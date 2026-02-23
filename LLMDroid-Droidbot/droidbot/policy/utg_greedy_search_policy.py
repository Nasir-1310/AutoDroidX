# droidbot/policy/utg_greedy_search_policy.py
from .input_policy import *
from .utg_based_policy import UtgBasedInputPolicy
from ..desc.action_type import ActionType
from ..utils import custom_serializer
import time
import random
import logging
import sys
import json

def get_logger():
    return logging.getLogger(__name__)

class UtgGreedySearchPolicy(UtgBasedInputPolicy):
    """
    DFS/BFS (according to search_method) strategy to explore UFG (new)
    """

    def __init__(self, device, app, random_input, search_method, code_coverage):
        super(UtgGreedySearchPolicy, self).__init__(device, app, random_input, code_coverage=code_coverage)
        self.logger = get_logger()
        self.search_method = search_method

        self.preferred_buttons = ["yes", "ok", "activate", "detail", "more", "access",
                                  "allow", "check", "agree", "try", "go", "next"]

        self.__nav_target = None
        self.__nav_num_steps = -1
        self.__num_restarts = 0
        self.__num_steps_outside = 0
        self.__event_trace = ""
        self.__missed_states = set()
        self.__random_explore = False

        # Load login credentials and hints from config
        self.config = getattr(app, 'config', {})
        self.credentials = self.config.get("LoginCredentials", [])
        self.hints = self.config.get("LoginHints", {
            "email_hints": ["email", "e-mail", "enter your email", "mail"],
            "username_hints": ["username", "user name", "enter your username", "user"],
            "password_hints": ["password", "pass", "enter your password"],
            "login_titles": ["login", "sign in", "log in"],
            "register_titles": ["register", "sign up", "create account"],
            "login_button_texts": ["login", "sign in", "log in"],
            "register_button_texts": ["register", "sign up", "create account"]
        })

        # Login state tracking
        self._login_event_queue = []       # queued events to return one-by-one
        self._credential_index = 0         # which credential to try next
        self._register_data_index = 0      # which RegisterFormData entry to try next
        self._login_success = False        # set True once login/register succeeds
        self._login_all_failed = False     # set True when all credentials exhausted
        self._awaiting_login_result = False # True right after we clicked the login button

        # Register form data
        self.register_form_data = self.config.get("RegisterFormData", [])

        self.logger.info(f"Loaded {len(self.credentials)} login credentials, "
                         f"{len(self.register_form_data)} register form data entries from config")

    # ──────────────────────────────────────────────
    # Login / Register helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _safe_str(val):
        """Convert value to lowercase string, handling None."""
        return str(val).lower() if val is not None else ""

    def _combined_text(self, view):
        """Build a single searchable string from a view dict using the correct key names."""
        return ' '.join([
            self._safe_str(view.get('text')),
            self._safe_str(view.get('content_description')),
            self._safe_str(view.get('resource_id'))
        ])

    def is_login_or_register_screen(self, state):
        """
        Detect whether the current state is a login or register screen.
        Returns (is_detected: bool, screen_type: str|None, button_view: dict|None)
        """
        if not state or not state.views:
            return False, None, None

        title_text = ""
        editable_count = 0
        has_email = False
        has_password = False
        has_username = False
        has_confirm_password = False
        has_first_name = False
        has_last_name = False
        has_phone = False
        has_age = False

        login_buttons = []
        register_buttons = []

        for view in state.views:
            combined = self._combined_text(view)

            # Detect title / screen type from any view text (case-insensitive)
            if any(t.lower() in combined for t in self.hints.get("login_titles", [])):
                title_text += "login "
            if any(t.lower() in combined for t in self.hints.get("register_titles", [])):
                title_text += "register "

            # Detect editable input fields
            if view.get('editable'):
                editable_count += 1
                if any(h.lower() in combined for h in self.hints.get("email_hints", [])):
                    has_email = True
                if any(h.lower() in combined for h in self.hints.get("password_hints", [])):
                    has_password = True
                if any(h.lower() in combined for h in self.hints.get("username_hints", [])):
                    has_username = True
                if any(h.lower() in combined for h in self.hints.get("confirm_password_hints", [])):
                    has_confirm_password = True
                if any(h.lower() in combined for h in self.hints.get("first_name_hints", [])):
                    has_first_name = True
                if any(h.lower() in combined for h in self.hints.get("last_name_hints", [])):
                    has_last_name = True
                if any(h.lower() in combined for h in self.hints.get("phone_hints", [])):
                    has_phone = True
                if any(h.lower() in combined for h in self.hints.get("age_hints", [])):
                    has_age = True

            # Collect button candidates
            if view.get('clickable') and view.get('enabled'):
                btn_text = ' '.join([
                    self._safe_str(view.get('text')),
                    self._safe_str(view.get('content_description'))
                ])
                if any(b.lower() in btn_text for b in self.hints.get("login_button_texts", [])):
                    login_buttons.append(view)
                if any(b.lower() in btn_text for b in self.hints.get("register_button_texts", [])):
                    register_buttons.append(view)

        # ── Determine screen type ──
        # Register-specific fields are strong indicators of a registration form
        register_specific_count = sum([
            has_confirm_password, has_first_name, has_last_name, has_phone, has_age
        ])
        title_lower = title_text.lower().strip()

        # A typical login page has 2-3 editable fields (email/username + password)
        # and NO register-specific fields.  Both pages may show the word "register"
        # (e.g. "Don't have an account? Register") so we CANNOT rely on title alone.
        #
        # Decision tree:
        #   1. If register-specific fields exist AND >=4 editable → register
        #   2. If only 2-3 editable fields and NO register-specific fields → login
        #   3. If >=4 editable AND register-specific → register
        #   4. Title-only fallback (only when fields are ambiguous)

        if register_specific_count >= 2:
            # Strong register signal: multiple register-only fields
            screen_type = "register"
        elif editable_count <= 3 and register_specific_count == 0:
            # Classic login: email + password (+ maybe username), no register fields
            screen_type = "login"
        elif editable_count >= 4 and register_specific_count >= 1:
            # Many fields + at least one register-specific → register
            screen_type = "register"
        elif editable_count >= 4:
            # 4+ fields, none register-specific – still likely register
            screen_type = "register"
        elif register_specific_count == 1 and editable_count <= 3:
            # Edge case: one register field but few editable → login (e.g. field mis-match)
            screen_type = "login"
        elif "login" in title_lower or "sign in" in title_lower:
            screen_type = "login"
        elif has_password and (has_email or has_username):
            screen_type = "login"
        else:
            screen_type = None

        # ── Select button matching the determined screen type ──
        action_button = None
        if screen_type == "register":
            if register_buttons:
                action_button = register_buttons[0]
            elif login_buttons:
                action_button = login_buttons[0]  # fallback
        elif screen_type == "login":
            if login_buttons:
                action_button = login_buttons[0]
            elif register_buttons:
                action_button = register_buttons[0]  # fallback

        # Must have password field + at least one identity field + a button
        is_detected = has_password and (has_email or has_username) and action_button is not None

        self.logger.debug(
            f"Screen detect: type={screen_type}, editable={editable_count}, "
            f"email={has_email}, pass={has_password}, user={has_username}, "
            f"confirm_pass={has_confirm_password}, first_name={has_first_name}, "
            f"last_name={has_last_name}, phone={has_phone}, age={has_age}, "
            f"register_specific={register_specific_count}, "
            f"login_btns={len(login_buttons)}, reg_btns={len(register_buttons)}, "
            f"title='{title_text.strip()}'"
        )
        return is_detected, screen_type, action_button

    def _find_field(self, views, hint_keys):
        """Find the first editable view whose text/resource_id matches any hint (case-insensitive)."""
        for view in views:
            if not view.get('editable'):
                continue
            combined = self._combined_text(view)
            if any(h.lower() in combined for h in hint_keys):
                return view
        return None

    def _get_all_editable_fields(self, state):
        """Return a list of all editable views on the current screen."""
        return [v for v in state.views if v.get('editable')]

    def _llm_fill_unknown_fields(self, unfilled_fields):
        """
        Use LLM to generate appropriate values for register fields that
        could not be matched by any config hint.

        Args:
            unfilled_fields: list of (view, label_text) tuples

        Returns:
            dict mapping label_text -> generated_value
        """
        if not unfilled_fields:
            return {}

        labels = [label for _, label in unfilled_fields]
        prompt = (
            "You are filling out a mobile app registration form for testing purposes. "
            "For each form field below, generate a single realistic fake value. "
            "Return ONLY a valid JSON object mapping each field label to its value. "
            "No explanation, no markdown, just the JSON.\n\n"
            "Fields:\n" + "\n".join(f'- "{label}"' for label in labels)
        )

        try:
            from openai import OpenAI
            api_key = self.config.get("ApiKey", "")
            base_url = self.config.get("BaseUrl", None)
            model = self.config.get("Model", "llama-3.1-8b-instant")

            if not api_key:
                self.logger.warning("LLM fallback: no ApiKey in config")
                return {}

            client_kwargs = {'api_key': api_key}
            if base_url:
                client_kwargs['base_url'] = base_url
            client = OpenAI(**client_kwargs)

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            content = response.choices[0].message.content.strip()
            self.logger.info(f"LLM fallback raw response: {content}")

            # Extract JSON from response (may be wrapped in markdown code block)
            import re
            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                self.logger.info(f"LLM generated values for {len(result)} fields")
                return result
            else:
                self.logger.warning("LLM fallback: could not parse JSON from response")
        except Exception as e:
            self.logger.warning(f"LLM fallback failed: {e}")

        return {}

    def _build_login_events(self, state, credential, button_view, screen_type="login"):
        """
        Build a list of InputEvents (SetText + Touch) for one login/register attempt.
        Returns a list of events, or empty list if required fields are missing.
        """
        from ..input_event import SetTextEvent, TouchEvent

        events = []

        if screen_type == "register":
            return self._build_register_events(state, button_view)

        # ── LOGIN path ──
        email = credential.get("email", "")
        username = credential.get("username", "")
        password = credential.get("password", "")

        email_view = self._find_field(state.views, self.hints.get("email_hints", []))
        username_view = self._find_field(state.views, self.hints.get("username_hints", []))
        password_view = self._find_field(state.views, self.hints.get("password_hints", []))

        if not password_view or not button_view:
            self.logger.warning("Login: missing password field or button – cannot build events")
            return []
        if not email_view and not username_view:
            self.logger.warning("Login: no email/username field found – cannot build events")
            return []

        if email_view and email:
            events.append(SetTextEvent(view=email_view, text=email))
        elif email_view and username:
            events.append(SetTextEvent(view=email_view, text=username))

        if username_view and username:
            events.append(SetTextEvent(view=username_view, text=username))
        elif username_view and email:
            events.append(SetTextEvent(view=username_view, text=email))

        events.append(SetTextEvent(view=password_view, text=password))
        events.append(TouchEvent(view=button_view))
        return events

    def _build_register_events(self, state, button_view):
        """
        Build events for a registration form:
         1. Fill every field matched by config hints using RegisterFormData
         2. For unmatched editable fields, call LLM to generate values
         3. Click the register button
        """
        from ..input_event import SetTextEvent, TouchEvent

        events = []
        filled_view_ids = set()  # track which views we already filled

        # Pick the register data entry
        reg_list = self.register_form_data
        if reg_list:
            reg_idx = self._register_data_index % len(reg_list)
            register_data = reg_list[reg_idx]
        else:
            register_data = {}

        # Ordered field mappings — order matters so password fields come last
        field_mappings = [
            ("first_name",        self.hints.get("first_name_hints", []),        register_data.get("first_name", "")),
            ("last_name",         self.hints.get("last_name_hints", []),         register_data.get("last_name", "")),
            ("username",          self.hints.get("username_hints", []),          register_data.get("username", "")),
            ("email",             self.hints.get("email_hints", []),             register_data.get("email", "")),
            ("phone",             self.hints.get("phone_hints", []),             register_data.get("phone", "")),
            ("age",               self.hints.get("age_hints", []),               register_data.get("age", "")),
            ("password",          self.hints.get("password_hints", []),          register_data.get("password", "")),
            ("confirm_password",  self.hints.get("confirm_password_hints", []),  register_data.get("confirm_password", "")),
        ]

        # Step 1: Fill fields matched by hints
        for field_name, hints, data in field_mappings:
            field_view = self._find_field(state.views, hints)
            if field_view and data:
                view_id = id(field_view)
                if view_id not in filled_view_ids:
                    self.logger.info(f"Register: filling '{field_name}' with '{data}'")
                    events.append(SetTextEvent(view=field_view, text=data))
                    filled_view_ids.add(view_id)

        # Step 2: Identify unfilled editable fields for LLM fallback
        all_editable = self._get_all_editable_fields(state)
        unfilled_fields = []
        for view in all_editable:
            if id(view) not in filled_view_ids:
                label = self._safe_str(view.get('text')) or self._safe_str(view.get('content_description')) or "unknown field"
                if label and label != "none" and label.strip():
                    unfilled_fields.append((view, label.strip()))

        if unfilled_fields:
            self.logger.info(f"Register: {len(unfilled_fields)} unfilled field(s) — calling LLM: "
                             f"{[lbl for _, lbl in unfilled_fields]}")
            llm_values = self._llm_fill_unknown_fields(unfilled_fields)

            for view, label in unfilled_fields:
                value = llm_values.get(label, "")
                if not value:
                    # Try partial key matching in LLM response
                    for key, val in llm_values.items():
                        if key.lower() in label.lower() or label.lower() in key.lower():
                            value = val
                            break
                if value:
                    self.logger.info(f"Register (LLM): filling '{label}' with '{value}'")
                    events.append(SetTextEvent(view=view, text=str(value)))
                    filled_view_ids.add(id(view))
                else:
                    self.logger.warning(f"Register: could not fill field '{label}' — no config or LLM data")

        if not events:
            self.logger.warning("Register: no fields could be filled – cannot build events")
            return []

        # Step 3: Click register button
        events.append(TouchEvent(view=button_view))

        self.logger.info(f"Register: built {len(events)} events ({len(events)-1} fields + 1 button click)")
        return events

    # ──────────────────────────────────────────────
    # Main event generation
    # ──────────────────────────────────────────────

    def generate_event_based_on_utg(self):
        """
        generate an event based on current UTG
        @return: InputEvent
        """
        current_state = self.current_state
        self.logger.info("Current state: %s" % current_state.state_str)
        if current_state.state_str in self.__missed_states:
            self.__missed_states.remove(current_state.state_str)

        # ═══════ LOGIN / REGISTER HANDLING ═══════

        # 1. If we have queued login/register events, return the next one
        if self._login_event_queue:
            event = self._login_event_queue.pop(0)
            if not self._login_event_queue:
                self._awaiting_login_result = True
            self.logger.info(f"Returning queued event ({type(event).__name__}), {len(self._login_event_queue)} remaining")
            self.__event_trace += EVENT_FLAG_EXPLORE
            return event

        # 2. If we just clicked the login/register button, check whether it worked
        if self._awaiting_login_result:
            self._awaiting_login_result = False
            detected, detected_type, _ = self.is_login_or_register_screen(current_state)
            if not detected:
                self.logger.info(f"Login/Register SUCCESS! Screen changed — proceeding normally.")
                self._login_success = True
                self.__random_explore = False
                # fall through to normal exploration
            else:
                self.logger.warning(f"Attempt did not work, still on {detected_type} screen.")
                # will try next credential/data below

        # 3. If login hasn't succeeded yet, try next credential or register data
        if not self._login_success and not self._login_all_failed:
            detected, screen_type, button_view = self.is_login_or_register_screen(current_state)
            if detected:
                if screen_type == "register":
                    # ── REGISTER flow ──
                    max_register = max(len(self.register_form_data), 1)
                    if self._register_data_index < max_register:
                        self.logger.info(
                            f"Register attempt {self._register_data_index + 1}/{max_register}"
                        )
                        events = self._build_login_events(current_state, {}, button_view, screen_type)
                        self._register_data_index += 1
                        if events:
                            self._login_event_queue = events[1:]
                            if not self._login_event_queue:
                                self._awaiting_login_result = True
                            self.__event_trace += EVENT_FLAG_EXPLORE
                            return events[0]
                        else:
                            self.logger.warning("Could not build register events")
                    else:
                        self.logger.warning("All register data exhausted – proceeding with exploration")
                        self._login_all_failed = True
                else:
                    # ── LOGIN flow ──
                    if self._credential_index < len(self.credentials):
                        cred = self.credentials[self._credential_index]
                        self._credential_index += 1
                        events = self._build_login_events(current_state, cred, button_view, screen_type)
                        if events:
                            self.logger.info(
                                f"Trying login credential {self._credential_index}/{len(self.credentials)}: "
                                f"email={cred.get('email','')}, user={cred.get('username','')}"
                            )
                            self._login_event_queue = events[1:]
                            if not self._login_event_queue:
                                self._awaiting_login_result = True
                            self.__event_trace += EVENT_FLAG_EXPLORE
                            return events[0]
                        else:
                            self.logger.warning(f"Could not build login events for credential {self._credential_index}")
                    else:
                        self.logger.warning("All login credentials exhausted – falling back to normal exploration")
                        self._login_all_failed = True

        # ═══════ ORIGINAL EXPLORATION LOGIC ═══════
        if current_state.get_app_activity_depth(self.app) < 0:
            # If the app is not in the activity stack
            start_app_intent = self.app.get_start_intent()

            # It seems the app stucks at some state, has been
            # 1) force stopped (START, STOP)
            #    just start the app again by increasing self.__num_restarts
            # 2) started at least once and cannot be started (START)
            #    pass to let viewclient deal with this case
            # 3) nothing
            #    a normal start. clear self.__num_restarts.

            if self.__event_trace.endswith(EVENT_FLAG_START_APP + EVENT_FLAG_STOP_APP) \
                    or self.__event_trace.endswith(EVENT_FLAG_START_APP):
                self.__num_restarts += 1
                self.logger.info("The app had been restarted %d times.", self.__num_restarts)
            else:
                self.__num_restarts = 0

            # pass (START) through
            if not self.__event_trace.endswith(EVENT_FLAG_START_APP):
                if self.__num_restarts > MAX_NUM_RESTARTS:
                    # If the app had been restarted too many times, enter random mode
                    msg = "The app had been restarted too many times. Entering random mode."
                    self.logger.info(msg)
                    self.__random_explore = True
                else:
                    # Start the app
                    self.__event_trace += EVENT_FLAG_START_APP
                    self.logger.info("Trying to start the app...")
                    return IntentEvent(intent=start_app_intent, action_type=ActionType.START)

        elif current_state.get_app_activity_depth(self.app) > 0:
            # If the app is in activity stack but is not in foreground
            self.__num_steps_outside += 1

            if self.__num_steps_outside > MAX_NUM_STEPS_OUTSIDE:
                # If the app has not been in foreground for too long, try to go back
                if self.__num_steps_outside > MAX_NUM_STEPS_OUTSIDE_KILL:
                    stop_app_intent = self.app.get_stop_intent()
                    go_back_event = IntentEvent(stop_app_intent, action_type=ActionType.STOP)
                else:
                    go_back_event = KeyEvent(name="BACK")
                self.__event_trace += EVENT_FLAG_NAVIGATE
                self.logger.info("Going back to the app...")
                return go_back_event
        else:
            # If the app is in foreground
            self.__num_steps_outside = 0

        # Get all possible input events
        possible_events = current_state.get_possible_input()

        if self.random_input:
            random.shuffle(possible_events)

        if self.search_method == POLICY_GREEDY_DFS:
            possible_events.append(KeyEvent(name="BACK"))
        elif self.search_method == POLICY_GREEDY_BFS:
            possible_events.insert(0, KeyEvent(name="BACK"))

        # get humanoid result, use the result to sort possible events
        # including back events
        if self.device.humanoid is not None:
            possible_events = self.__sort_inputs_by_humanoid(possible_events)

        # If there is an unexplored event, try the event first
        for input_event in possible_events:
            if not self.utg.is_event_explored(event=input_event, state=current_state):
                self.logger.info("Trying an unexplored event.")
                self.__event_trace += EVENT_FLAG_EXPLORE
                return input_event

        target_state = self.__get_nav_target(current_state)
        if target_state:
            navigation_steps = self.utg.get_navigation_steps(from_state=current_state, to_state=target_state)
            if navigation_steps and len(navigation_steps) > 0:
                self.logger.info("Navigating to %s, %d steps left." % (target_state.state_str, len(navigation_steps)))
                self.__event_trace += EVENT_FLAG_NAVIGATE
                return navigation_steps[0][1]

        if self.__random_explore:
            self.logger.info("Trying random event.")
            random.shuffle(possible_events)
            return possible_events[0]

        # If couldn't find a exploration target, stop the app
        stop_app_intent = self.app.get_stop_intent()
        self.logger.info("Cannot find an exploration target. Trying to restart app...")
        self.__event_trace += EVENT_FLAG_STOP_APP
        return IntentEvent(intent=stop_app_intent, action_type=ActionType.STOP)

    def __sort_inputs_by_humanoid(self, possible_events):
        if sys.version.startswith("3"):
            from xmlrpc.client import ServerProxy
        else:
            from xmlrpclib import ServerProxy
        proxy = ServerProxy("http://%s/" % self.device.humanoid)
        request_json = {
            "history_view_trees": self.humanoid_view_trees,
            "history_events": [x.__dict__ for x in self.humanoid_events],
            "possible_events": [x.__dict__ for x in possible_events],
            "screen_res": [self.device.display_info["width"],
                           self.device.display_info["height"]]
        }
        result = json.loads(proxy.predict(json.dumps(request_json, default=custom_serializer)))
        new_idx = result["indices"]
        text = result["text"]
        new_events = []

        # get rid of infinite recursive by randomizing first event
        if not self.utg.is_state_reached(self.current_state):
            new_first = random.randint(0, len(new_idx) - 1)
            new_idx[0], new_idx[new_first] = new_idx[new_first], new_idx[0]

        for idx in new_idx:
            if isinstance(possible_events[idx], SetTextEvent):
                possible_events[idx].text = text
            new_events.append(possible_events[idx])
        return new_events

    def __get_nav_target(self, current_state):
        # If last event is a navigation event
        if self.__nav_target and self.__event_trace.endswith(EVENT_FLAG_NAVIGATE):
            navigation_steps = self.utg.get_navigation_steps(from_state=current_state, to_state=self.__nav_target)
            if navigation_steps and 0 < len(navigation_steps) <= self.__nav_num_steps:
                # If last navigation was successful, use current nav target
                self.__nav_num_steps = len(navigation_steps)
                return self.__nav_target
            else:
                # If last navigation was failed, add nav target to missing states
                self.__missed_states.add(self.__nav_target.state_str)

        reachable_states = self.utg.get_reachable_states(current_state)
        if self.random_input:
            random.shuffle(reachable_states)

        for state in reachable_states:
            # Only consider foreground states
            if state.get_app_activity_depth(self.app) != 0:
                continue
            # Do not consider missed states
            if state.state_str in self.__missed_states:
                continue
            # Do not consider explored states
            if self.utg.is_state_explored(state):
                continue
            self.__nav_target = state
            navigation_steps = self.utg.get_navigation_steps(from_state=current_state, to_state=self.__nav_target)
            if navigation_steps and len(navigation_steps) > 0:
                self.__nav_num_steps = len(navigation_steps)
                return state

        self.__nav_target = None
        self.__nav_num_steps = -1
        return None
