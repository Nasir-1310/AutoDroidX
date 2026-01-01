from .input_event import TouchEvent, UIEvent, SetTextEvent
from .image_comparer import ImageComparer

class CustomTouchEvent(TouchEvent):

    def send(self, device):
        if self.view and self.view['class'] and ("Button" not in self.view['class'] and "EditText" not in self.view['class']):
            return True
        if self.view and "Button" in self.view['class'] and self.view['clickable']:
            before = device.take_screenshot()
            print(f'Before Image: {before}')
            x, y = UIEvent.get_xy(x=self.x, y=self.y, view=self.view)
            device.view_long_touch(x=x, y=y, duration=200)
            import time
            time.sleep(1.5)
            after = device.take_screenshot()
            print(f'After Image: {after}')
            result = ImageComparer.compareImage(before, after)

            import json
            import re

            match = re.search(r'\{.*\}', result, re.DOTALL)

            if match:
                json_str = match.group(0) 
                parsed_data = json.loads(json_str)

                print('\n\n\n')
                print(f'Verdict = {parsed_data["verdict"]}')
                print(f'Response = {parsed_data["response"]}')
                print('\n\n\n')
                # if "Navigation" in parsed_data["response"] or parsed_data['verdict'] == 'fail':
                #     import os, time
                #     device.set_last_known_state()
                #     time.sleep(2)
                #     os.system("adb shell input keyevent KEYCODE_BACK")
                    
            else:
                print("No JSON found in the text.")

        else:
            x, y = UIEvent.get_xy(x=self.x, y=self.y, view=self.view)
            device.view_long_touch(x=x, y=y, duration=200)
        return True
    


class CustomSetTextEvent(SetTextEvent):

    def send(self, device):
        # import os
        # os.system("adb shell input keyevent KEYCODE_BACK")
        # return True
        x, y = UIEvent.get_xy(x=self.x, y=self.y, view=self.view)
        touch_event = TouchEvent(x=x, y=y)
        touch_event.send(device)


        # Saimon Bhuiyan (SPL2)
        from .GeminiAI import GeminiAi

        input_list = GeminiAi.generate_random_input()
        if input_list is not None:
            input_string = "".join(map(str, input_list.values()))
            if self.view["text"] in input_string or "Enter" not in self.view["text"]:
                device.view_set_text(self.view["text"])
                return True
        print(input_list)
        chat = GeminiAi.get_chat()
        response = chat.send_message(f'prompt: {self.view["text"]}, {self.get_event_str(device.get_current_state()) if ("Login" or "Sign") in self.get_event_str(device.get_current_state()) else ""}')
        text = input_list[response.text.strip()]
        if not text:
            text = ""
        device.view_set_text(text)
        
        return True
