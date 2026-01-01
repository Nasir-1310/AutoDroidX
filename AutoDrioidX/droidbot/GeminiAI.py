import google.generativeai as genai
import pathlib
import json

media = pathlib.Path(__file__).parents[1] / "droidbot"

class GeminiAi:
    _chat = None
    _input = None
    genai.configure(api_key="AIzaSyDy_VQnRxk5LqrOvEtpdZzxXdM8tIt_0xg")
    __model = genai.GenerativeModel("gemini-1.5-flash-latest")

    @classmethod
    def parse_json(cls, json_string: str):
        try:
            json_string = json_string.strip()
            json_lines = json_string.split('\n')
            json_string = '\n'.join(json_lines[1:-1])
            json_data = json.loads(json_string)
            return json_data
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return None
    @classmethod
    def get_chat(cls):
        if cls._chat is None:
            _system_prompt = f'You are an android input test case generator tool called Testcube. Your work is to find best input for a input field.I have some existing credential input. Here is the credentials i have. Credentials: \n{cls._input}. Now after every input field found i will give you a prompt. The prompt will look like "Enter your email" / "Enter Password" / "Username" etc also there can be an optional event_str look like "SetTextEvent(state=471db0b34dd4b9be2ac8f0917d8e947a, view=23945eb0f968dd6ba05de8382ade54e1(Login)/EditText-Enter your), text=)". From the event_str you can get knowledge about what page are you in now so use credential accordingly. Your work is to find for this prompt what existing credential i should use. My credentials are in key value format. You have to give me the key name only with proper case maintained. If you found something that that is not your prompt type like if you encounter a prompt example@gmail.com then you have to be smart and send response as email because this value belong to an email.Also if you found **** then it must be a password so respond pass. So finally just dont look for the key name if you found something that matches any value in the existing credential then also repond the corresponding key name.\nExample:\nCredentials:\nemail: saimon@gmail.com\npass: 12345678\nprompt: Enter your email\nresponse: email\nprompt: Enter Password\nresponse: pass\nprompt: Bhuiyan\nresponse: l_name.\nAlso use credentials that are actual_... only for Login page any type of login page for first time, otherwise use random credentials. Like if i ask for email then one time give me email5 then next time give me email7. Use randomize value.'
            cls._chat = cls.__model.start_chat(
                history=[
                    {"role": "user", "parts": _system_prompt},
                ]
            )
        return cls._chat
    
    @classmethod
    def generate_random_input(cls):
        if cls._input is None:
            credential_content = ""
            with open(media / "credential.txt", "r") as f:
                credential_content += f.read()
            _system_prompt = f'You are an android input test case generator tool called Testcube. Your work is to simulate mock data to test an android app. I have some existing credentials input for testing. Here is the credentials i have. Credentials:\n{credential_content}. Now you need to create exactly 10 copy of this credentials in json format and return me a json. For each variation consider empty string, variatiion in gmail format, variation in password length, variation in upper case lower case etc but try to be real. Also create variation in all of the field. Finally return me a json where my given credentials key should be named "actual_email": "example@gmail.com", "actual_pass": "12345678" etc. And the 10 variation should be like "email1": "something@gmail.com" and so on and all the key and value should properly double quoted.'
            chat = cls.__model.start_chat(
                history = [
                    {"role": "user", "parts": _system_prompt}
                ]
            )
            response = chat.send_message("Generate now")
            cls._input = cls.parse_json(response.text)
            print(cls._input)
        return cls._input