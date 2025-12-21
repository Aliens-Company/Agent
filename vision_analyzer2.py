from openai import AzureOpenAI
from config import AZURE_API_KEY, AZURE_ENDPOINT, AZURE_API_VERSION, LLM_DEPLOYMENT
import json


class VisionAnalzer:
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=AZURE_API_KEY,
            azure_endpoint=AZURE_ENDPOINT,
            api_version=AZURE_API_VERSION
        )
        self.deployment = LLM_DEPLOYMENT

    def analyze_screen(self, base64_image, command):
        if not base64_image:
            return None
        
        prompt = f"""Is screenshot mein {command} icon dhoondho aur uska center point ka X,Y coordinates json format me do
        Return ONLY valid JSON.
        Example: {{"x":125,"y":340}}
        Sirf numbers aur comma, kuch aur mat likhna."""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type":"text","text":prompt},
                            {
                                "type":"image_url",
                                "image_url":{
                                    "url":f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.1
            )

            analysis_result = response.choices[0].message.content
            print(analysis_result)
            print(type(analysis_result))

            cleaned_result = analysis_result.strip()

            if cleaned_result.startswith("```json"):
                cleaned_result = cleaned_result[7:]

            if cleaned_result.endswith("```"):
                cleaned_result = cleaned_result[:-3]

            cleaned_result = cleaned_result.strip()
            print(cleaned_result)

            vision_data = json.loads(cleaned_result)
            print(vision_data)
            print(type(vision_data))

           

            return vision_data
        except Exception as e:
            print("Error when vision analysis ") 
            return None
