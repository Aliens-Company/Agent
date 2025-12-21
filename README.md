# Aliens Agent

एक ही रिपॉज़िटरी में दो अलग-अलग ऑटोमेशन सिस्टम मौजूद हैं:

1. **ChatGPT automation bot** – Selenium की मदद से ChatGPT वेब UI में पेज प्लान और कोड डाउनलोड करने वाला वर्कफ़्लो चलाता है।
2. **Desktop autonomous loop** – लोकल स्क्रीन का स्क्रीनशॉट लेकर Azure OpenAI विज़न मॉडल से UI एलिमेंट ढूंढता है और PyAutoGUI के जरिए क्लिक कर देता है।

दोनों सिस्टम स्वतंत्र हैं, लेकिन एक ही `requirements.txt` और कुछ सपोर्ट फाइलें शेयर करते हैं। यह दस्तावेज़ पूरी संरचना, डिपेंडेंसी, कॉन्फ़िगरेशन और रनबुक को कवर करता है।

## फ़ोल्डर संरचना

- `ChatGPT.py` – मुख्य Selenium ड्राइवर, प्रॉम्प्ट और डाउनलोड मैनेजमेंट लॉजिक।
- `autonomous_loop.py` – डेस्कटॉप एजेंट का हाई-लेवल ऑर्केस्ट्रेटर।
- `vision_analyzer2.py` – Azure OpenAI विज़न कॉल्स और JSON पोस्ट-प्रोसेसिंग।
- `screen_capture2.py` – MSS + Pillow से स्क्रीनशॉट लेना और base64 एनकोड करना।
- `text_input.py` – CLI के जरिए यूज़र कमांड लेना और डेस्कटॉप तैयार करना।
- `action_execution2.py` – PyAutoGUI के जरिए किसी पॉइंट पर क्लिक करवाना।
- `config.py` – API keys, endpoints और ChatGPT सत्र URL। (प्रोडक्शन में env vars इस्तेमाल करें।)
- `prompts.csv` / `aliens_school_webpages.json` – पेज नाम और प्रॉम्प्ट टेम्पलेट डेटा-सोर्स।
- `todo.csv` / `todo.json` – प्रॉसेस किए गए पेजों की ट्रैकिंग (ज़रूरत पर `ChatGPT.py` खुद बनाता है)।

## पूर्व-आवश्यकताएँ

- Python 3.10+
- Chrome + ChromeDriver (driver PATH पर उपलब्ध या Selenium Manager ऑटो डाउनलोड)
- Windows मशीन (PyAutoGUI और स्क्रीन कैप्चर सेटअप इसी पर ट्यून किया गया)
- Azure OpenAI विज़न मॉडल एक्सेस (deployment name `LLM_DEPLOYMENT` के रूप में)
- ChatGPT Plus खाते में उस कस्टम GPT का एक्सेस जिसकी URL `config.py` में है

## इंस्टॉलेशन

```bash
pip install -r requirements.txt
```

फ़ाइल में शामिल मुख्य पैकेज: `selenium`, `pyautogui`, `openai`, `mss`, `Pillow`।

### ChromeDriver नोट्स
- यदि ChromeDriver mismatch हो, तो matching version डाउनलोड करें या `webdriver-manager` के जरिए हैंडल करें।
- `ChatGptAutomation` कस्टम यूज़र-प्रोफाइल लेने के लिए `profile_path` और `profile_name` arguments सपोर्ट करता है।

## कॉन्फ़िगरेशन

`config.py` में मौजूद मानों को सीधे कमिट नहीं करना चाहिए। सुरक्षित तरीके:

- `AZURE_API_KEY`, `AZURE_ENDPOINT`, `AZURE_API_VERSION`, `LLM_DEPLOYMENT` को environment variables के रूप में सेट करें और `config.py` में `os.getenv` के जरिए रीफरेंस करें।
- `CHAT_SESSION_URL` को उस GPT चैट URL से अपडेट रखें जिसे Selenium ऑटोमेट करता है।

## ChatGPT Automation वर्कफ़्लो (`ChatGPT.py`)

1. Selenium Chrome से ChatGPT conversation पेज खोलता है।
2. `aliens_school_webpages.json` से हर पेज नाम पर लूप चलता है।
3. हर पेज के लिए `prompts.csv` से तीन टेम्पलेट लोड होते हैं:
	- प्रॉम्प्ट 1: detailed planning
	- प्रॉम्प्ट 2: downloadable कोड
	- प्रॉम्प्ट 3: वैकल्पिक/अतिरिक्त आउटपुट (फाइल डाउनलोड का दूसरा प्रयास)
4. `create_new_branch_switch_driver()` नया ब्रांच चैट बनाता है ताकि मेन थ्रेड साफ रहे।
5. `type_text()` textarea में प्रॉम्प्ट डालता है, Enter करता है।
6. `check_response_complete()` “Stop generating” बटन गायब होने तक वेट करता है।
7. `scroll_until_link_present()` और `download_file()` download लिंक तक स्क्रॉल करके क्लिक करते हैं।
8. सफल होने पर `todo.csv` में status अपडेट होता है, URL सेव होता है, और टैब बंद कर दिया जाता है।

> लॉग्स `GptBot.log` में सेव होते हैं। हर रन में फाइल रीसेट होती है (mode=`"w"`).

### रन कैसे करें

```bash
python ChatGPT.py
```

यदि Selenium `NoSuchElementException` या मॉड्यूल मिसिंग एरर दे, तो:

- सुनिश्चित करें कि लॉग-इन session मौजूद है (user-data-dir/Chrome profile पास करें)।
- `pip install selenium` आदि चलाकर dependencies पूरा करें।

## Autonomous Desktop एजेंट वर्कफ़्लो

कुल फ्लो `main.py` → `AutonomousLoop.run_autonomous_agent()` इस तरह चलता है:

1. `UserTextInput.get_user_command()` टर्मिनल से नैचुरल-लैंग्वेज कमांड लेता है और `Win+D` से डेस्कटॉप साफ करता है।
2. `ScreenCapture.capture_and_encode()` पूरे मॉनिटर का PNG बेस64 बनाता है।
3. `VisionAnalzer.analyze_screen()` Azure OpenAI Vision से `{ "x": ..., "y": ... }` JSON रिटर्न करवाता है।
4. `ActionExecuter.action_execution()` PyAutoGUI से उस पॉइंट पर move + click करता है।

### रन कैसे करें

```bash
python main.py
```

कमांड का उदाहरण:

- “Chrome icon pe click karo”
- “To Do open karo”

> Vision मॉडल से वापस आने वाला JSON strictly numeric होना चाहिए; यदि तीन बैकटिक्स (` ```json `) के साथ आता है तो `vision_analyzer2.py` उसे sanitize कर देता है।

## डेटा फाइल्स

- `aliens_school_webpages.json` – key/value मैप, हर value एक page name है।
- `prompts.csv` – `id` (`1`, `2`, `3`) और `prompt` कॉलम। प्लेसहोल्डर `{page_name}` रन-टाइम पर रिप्लेस होता है।
- `todo.csv` – `status` (`0` pending, `1` done) और `url` कॉलम; पहली रन पर ऑटो-जनरेट हो सकती है।

## ट्रबलशूटिंग

- **Missing selenium** – `pip install selenium` या दुबारा `pip install -r requirements.txt` चलाएँ।
- **ChromeDriver mismatch** – सिस्टम में Chrome अपडेट होने पर नया ड्राइवर अनिवार्य।
- **PyAutoGUI permissions** – Windows में “Change my settings for quick access” या accessibility अनुमति की ज़रूरत पड़ सकती है।
- **Azure OpenAI errors** – Deployment नाम, endpoint और API version वैलिड हों।

## आगे क्या?

- `config.py` को environment-driven बनाना (secrets repo में न रहें)।
- Vision response के लिए schema validation / retries जोड़ना।
- Autonomous एजेंट के लिए multi-step planning या feedback loop इम्प्लीमेंट करना।

इतनी जानकारी से अब `Agent` repo की आर्किटेक्चर और रनबुक दोनों स्पष्ट हो जाते हैं।