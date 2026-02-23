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
        self._login_success = False        # set True once login/register succeeds
        self._login_all_failed = False     # set True when all credentials exhausted
        self._awaiting_login_result = False  # True right after we clicked the login button

        self.logger.info(f"Loaded {len(self.credentials)} login credentials from config")

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
        has_email = False
        has_password = False
        has_username = False
        action_button = None
        screen_type = None

        for view in state.views:
            combined = self._combined_text(view)

            # Detect title / screen type from any view text
            if any(t in combined for t in self.hints.get("login_titles", [])):
                title_text += "login "
            if any(t in combined for t in self.hints.get("register_titles", [])):
                title_text += "register "

            # Detect editable input fields
            if view.get('editable'):
                if any(h in combined for h in self.hints.get("email_hints", [])):
                    has_email = True
                if any(h in combined for h in self.hints.get("password_hints", [])):
                    has_password = True
                if any(h in combined for h in self.hints.get("username_hints", [])):
                    has_username = True

            # Detect login/register button
            if view.get('clickable') and view.get('enabled'):
                btn_text = ' '.join([
                    self._safe_str(view.get('text')),
                    self._safe_str(view.get('content_description'))
                ])
                if any(b in btn_text for b in self.hints.get("login_button_texts", [])):
                    action_button = view
                    screen_type = "login"
                if any(b in btn_text for b in self.hints.get("register_button_texts", [])):
                    action_button = view
                    screen_type = "register"

        # Require at least: password field + (email or username) + a button
        # Don't require title text – many apps don't have an explicit title
        is_detected = has_password and (has_email or has_username) and action_button is not None

        self.logger.debug(
            f"Login detect: email={has_email}, pass={has_password}, user={has_username}, "
            f"button={action_button is not None}, title='{title_text.strip()}', type={screen_type}"
        )
        return is_detected, screen_type, action_button

    def _find_field(self, views, hint_keys):
        """Find the first editable view whose text/resource_id matches any hint."""
        for view in views:
            if not view.get('editable'):
                continue
            combined = self._combined_text(view)
            if any(h in combined for h in hint_keys):
                return view
        return None

    def _build_login_events(self, state, credential, button_view):
        """
        Build a list of InputEvents (SetText + Touch) for one login/register attempt.
        Views already have 'widget' set by DeviceState.__init_widgets, so no need to recreate.
        Returns a list of events, or empty list if required fields are missing.
        """
        from ..input_event import SetTextEvent, TouchEvent

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

        events = []

        # Fill email field
        if email_view and email:
            events.append(SetTextEvent(view=email_view, text=email))
        elif email_view and username:
            # If no email credential but email field exists, try username in it
            events.append(SetTextEvent(view=email_view, text=username))

        # Fill username field (if separate from email)
        if username_view and username:
            events.append(SetTextEvent(view=username_view, text=username))
        elif username_view and email:
            events.append(SetTextEvent(view=username_view, text=email))

        # Fill password field
        events.append(SetTextEvent(view=password_view, text=password))

        # Click login/register button
        events.append(TouchEvent(view=button_view))

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

        # 1. If we have queued login events, return the next one
        if self._login_event_queue:
            event = self._login_event_queue.pop(0)
            # If this is the last event (the button click), mark that we're awaiting result
            if not self._login_event_queue:
                self._awaiting_login_result = True
            self.logger.info(f"Returning queued login event ({type(event).__name__}), {len(self._login_event_queue)} remaining")
            self.__event_trace += EVENT_FLAG_EXPLORE
            return event

        # 2. If we just clicked the login button, check whether it worked
        if self._awaiting_login_result:
            self._awaiting_login_result = False
            detected, _, _ = self.is_login_or_register_screen(current_state)
            if not detected:
                self.logger.info(f"Login/Register SUCCESS with credential {self._credential_index}! Proceeding normally.")
                self._login_success = True
                self.__random_explore = False
                # fall through to normal exploration
            else:
                self.logger.warning(f"Credential {self._credential_index} did not work, still on login/register screen.")
                # will try next credential below

        # 3. If login hasn't succeeded yet and we still have credentials, try next one
        if not self._login_success and not self._login_all_failed:
            detected, screen_type, button_view = self.is_login_or_register_screen(current_state)
            if detected:
                if self._credential_index < len(self.credentials):
                    cred = self.credentials[self._credential_index]
                    self._credential_index += 1
                    events = self._build_login_events(current_state, cred, button_view)
                    if events:
                        self.logger.info(
                            f"Trying credential {self._credential_index}/{len(self.credentials)}: "
                            f"email={cred.get('email','')}, user={cred.get('username','')}"
                        )
                        self._login_event_queue = events[1:]  # queue remaining
                        if not self._login_event_queue:
                            self._awaiting_login_result = True
                        self.__event_trace += EVENT_FLAG_EXPLORE
                        return events[0]  # return first event now
                    else:
                        self.logger.warning(f"Could not build login events for credential {self._credential_index}")
                        # try next credential on next cycle
                else:
                    self.logger.warning("All credentials exhausted – falling back to normal exploration")
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
