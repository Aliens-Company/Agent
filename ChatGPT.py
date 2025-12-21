import logging
import csv
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as Ec
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
import pyautogui
import json
from time import sleep, time

from config import CHAT_SESSION_URL

class ChatGptAutomation:
    def __init__(self, profile_path=None, profile_name=None):
        self._setup_logging()
        self.logger.info("Initializing GptBot....")

        
        chrome_options = Options()
        if profile_path:
            chrome_options.add_argument(f"--user-data-dir={profile_path}")
        
        if profile_name:
            chrome_options.add_argument(f"--profile-directory={profile_name}")

        chrome_options.add_argument("--no-sandbox")                                       # security sandbox disable.
        chrome_options.add_argument("--disable-dev-shm-usage")                            # chrome ko /dev/shm(shared memory) use karne se rokata hai.
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")      # chrome ke automation detection flag ko hide karta hai.
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])  # chrome ke upar jo banner aata hai use remove karta hai.
        chrome_options.add_experimental_option('useAutomationExtension', False)           # chrome ki automation extention ko disable karta hai.
        chrome_options.add_argument('--no-first-run')                                     # chrome ka first run setup remove karta hai yani welcome screen skip, setup dialog skip, chrome directly normal browsing mode me start.
        chrome_options.add_argument('--no-default-browser-check')                         # chrome popup (make chrome your defualt browser)
        chrome_options.add_argument(                                                      # ye chrome browser ka user agent string manualy set karta hai.
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            "AppleWebKit/537.36 (KHTML, like Gecko)"
            "Chrome/143.0.0.0 Safari/537.36"
        )

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.maximize_window()                                                      # window size ko maximize karta hai.
        self.action = ActionChains(self.driver)
        self.wait = WebDriverWait(self.driver, 40)

    def _setup_logging(self):            # ye ek private function hai logging setup ke liye.
        logging.basicConfig(             # logging system configure ho raha hai.
            level=logging.DEBUG,         # sabhi type ke log capture honge(DEBUG,ERROR,INFO,CRITICAL,WARNING).
            format='%(asctime)s - %(levelname)s - %(message)s',  # log ka look dicide karta hai.
            handlers=[                   # handlers batate hai log kaha kaha jana chahiye.
                logging.FileHandler("GptBot.log", mode="w"),  # Log GptBot.log name ki file me save hoga, or mode="w" ka matalb hai har run par purani log file clear.
                logging.StreamHandler()  # log terminal me show hoga.
            ]
        )
        self.logger = logging.getLogger("WebBot") # Yaha logging object create kiya hai name diya hai WebBot

    def open_url(self, url: str):
        """Ye function url ko open karta hai."""
        self.logger.info(f"Opning Url {url}")
        try:
            self.driver.get(url)
            sleep(3)
        except Exception as e:
            self.logger.error(f"Faild to open Url: {e}")

    def click_more_action_button(self, locator_type, locator):
        """ye function more action button par click karta hai """
        self.logger.info(f"Clicking element: {locator}")
        try:
            element = self.wait.until(Ec.presence_of_all_elements_located((locator_type, locator)))
            lenth = len(element)
            print(lenth)
            last_element = element[-1]
            self.logger.info(f"Element lenth: {lenth}")

            last_element.send_keys(Keys.ENTER)  # Iske bina element par click nhi ho sakata hai kisi bhi tarike se kyonki element div ke niche hai.
            
        except Exception as e:
            self.logger.error(f"Click faild: {e}")

    def type_text(self, locator_type, locator, text: str):
        """Ye funtion input field me text ko fill karta hai or send karta hai."""
        self.logger.info(f"Typing text in element {locator}")
        try:
            element = self.wait.until(Ec.visibility_of_element_located((locator_type, locator)))  # ye function element ka tab tak wait karega jab tak ki element visibile na ho jaye ya timeout tak. until() bar bar funtion call karta hai or check karta  rahata hai.Isme arguments tuple ke form me bheje jate hai.
            element.click()
            sleep(5)
            self.action.move_to_element(element).click().pause(0.1).send_keys(text).pause(0.1).send_keys(Keys.ENTER).perform()
            sleep(2)
        
        except Exception as e:
            self.logger.error(f"Failed to type text in element: {locator} message:{e}")

    def check_response_complete(
        self,
        send_button_locator,
        timeout: int = 180,
        poll_frequency: float = 1.0,
        confirmations_required: int = 2
    ):
        """Busy indicator(button) HTML me tab tak rehta hai jab tak response stream ho raha hota hai."""
        self.logger.info("Stop streaming button ka wait shuru")

        absence_streak = 0
        start_time = time()

        try:
            while time() - start_time <= timeout:
                element_present = bool(self.driver.find_elements(*send_button_locator))
                if element_present:
                    if absence_streak:
                        self.logger.debug("Button wapas DOM me aagya, streak reset.")
                    absence_streak = 0
                    self.logger.debug("Button abhi bhi DOM me hai, system busy hai.")
                else:
                    absence_streak += 1
                    self.logger.debug(
                        "Button %s bar absent mila (target %s)",
                        absence_streak,
                        confirmations_required
                    )
                    if absence_streak >= confirmations_required:
                        self.logger.info("Button DOM se gayab confirm ho gaya, ab next step run karenge.")
                        return True
                sleep(poll_frequency)

            self.logger.warning(
                "Button %s timeout %s sec ke baad bhi reliably gayab nahi hua, phir bhi aage badh rahe hain.",
                send_button_locator,
                timeout
            )
        except Exception as e:
            print(f"An Error when checking response button {e}")
            self.logger.error(f"Faild to check button invisibility {e}")

        return False

    def scroll_until_link_present(
        self,
        link_xpath: str,
        max_scrolls: int = 40,
        scroll_pause: float = 0.5
    ):
        """ Ye function second prompt ke send karne ke bad me call hoga or jaise hi ise download link dikhega ye page ko end tak scroll kar dega."""
    
        for scroll_count in range(max_scrolls):
            try:
                # STEP 1: DOM presence check
                link = self.driver.find_element(By.XPATH, link_xpath)

                self.logger.info(
                    "Target link found in DOM. Scrolling to bottom."
                )
                if link.is_displayed():
                    scroll_div = self.driver.find_element(By.TAG_NAME, 'body')
                    scroll_div.click()
                    scroll_div.send_keys(Keys.END)

                    return link

            except NoSuchElementException:
                self.logger.debug(
                    f"Scrolling attempt {scroll_count + 1}"
                )
                sleep(scroll_pause)

        self.logger.warning(
        "Target link not found after max scroll attempts. Continuing execution."
    )
        return None

    def download_file(self):
        """Ye function file download link par click karta hai or file download karta hai."""
        locator_type = By.XPATH
        locator = '//a[contains(normalize-space(.), "Download")]'
        self.logger.info("Clicking on download file element.")
        try: 
            element = self.wait.until(Ec.presence_of_element_located((locator_type, locator)))

            elements = self.driver.find_elements(By.XPATH, locator)

            if not elements:
                self.logger.warning("No download link found, skiping download ")
                return False

            last_element = elements[-1]
            self.action.move_to_element(last_element)\
            .pause(0.3)\
            .click()\
            .perform()
            sleep(5)
            return True
        except Exception as e:
            self.logger.error(f"Faild to download {e}")
            return False
  
    def create_new_branch_switch_driver(self):
        """Ye function new branch create karta hai or sath me driver ko main chat se brach wali chat pe switch karta hai"""
        locator_type = By.XPATH
        more_action_button_xpath = '//button[@aria-label="More actions"]'
        new_branch_button_selector = '//*[contains(text(),"Branch in new chat")]'

        try:
            self.old_tab1 = self.driver.current_window_handle   # Isaka use driver ko vapas main page par le jane ke liye kiya hai.
            self.old_tab = self.driver.window_handles           # Iska use driver ko branch wali tab par le jane ke liye kiya hai.

            self.click_more_action_button(locator_type,more_action_button_xpath)
            sleep(4)
            self.logger.info(f"Clicking element {new_branch_button_selector}")
            branch_button = self.wait.until(Ec.visibility_of_element_located((locator_type, new_branch_button_selector)))
            branch_button.click()

            new_tabs = self.driver.window_handles

            for tab in new_tabs:
                if tab  not in self.old_tab:
                    self.driver.switch_to.window(tab)  # window() function se driver switch kiya hai new branch ki tab par
                    break
        except Exception as e:
            self.logger.error(f"Click Faild: {e}")
  
        
    def load_page_prompt(self):
        """Ye function json file se ek ek karke promts ko utha raha hai or unhe generate kar raha gtp ko dene ke liye or prompts ko return kar raha hai."""
        try:
            filename = "aliens_school_webpages.json"
            with open(filename, "r") as file:
                data = file.read()
                json_text = json.loads(data)  # loads() function json string ko python data me convert karta hai.

            for page_name in json_text.values():
                yield self.generate_page_prompts(page_name)  # yeild function ko generator bana deta hai.
        
        except Exception as e:
            print(f"An Error occured when process prompts {e}")
        
    def load_prompts(self):
        try:
            with open("prompts.json", "r") as file:
                json_text = file.read()
                data = json.loads(json_text)
                prompt1 = data.get("1", "")
                prompt2 = data.get("2", "")
                prompt3 = data.get("3", "")

                return prompt1, prompt2, prompt3
        except json.JSONDecodeError:
            return
        
    def load_webpage_data(self):
        try:
            with open("aliens_school_webpages.json", "r") as file:
                json_text = file.read()
                data = json.loads(json_text) 

            for page_name in data.values():
                prompt1, prompt2, prompt3 = self.load_prompts()
                prompt1 = prompt1.format(page_name=page_name)
                prompt2 = prompt2.format(page_name=page_name)
                prompt3 = prompt3.format(page_name=page_name)

                yield prompt1, prompt2, prompt3
        except Exception as e:
            print(f"An Error occured when process prompts {e}")


    def generate_page_prompts(self, page_name:str) -> dict:
        """ye function prompt ko loop me chalane ke liye banaya hai"""

        if page_name:
            prompt1 = f"Webpage : {page_name}  is webpage ka complete plan do extra detail k saath jo ki meri website k design ko Enterprise Grade  ka bna de "
            prompt2 =  f"Webpage : {page_name}  ok to ab is planning ke hisab se download hone layak file me code likh k do download option ke sath without extra detail AliensStyle and Enterprise Grade ko dhyan me rakhte hue, yeh bhi dhyan rakhna hai k yeh  Aliens School ki website ke baaki pages sy milta julta ho or sath me onefile bana kar do download hone layak AliensStyle  Enterprise Grade Design  CleanCode  Premium Design "

            return {"1": prompt1, "2": prompt2}
        return {}

    def _ensure_tasks_csv(self, csv_filename: str = "aliens_school_webpages.csv", seed_json: str = "aliens_school_webpages.json") -> Path:
        csv_path = Path(csv_filename)
        if csv_path.exists():
            return csv_path

        json_path = Path(seed_json)
        if not json_path.exists():
            raise FileNotFoundError(f"Neither {csv_filename} nor {seed_json} found")

        with open(json_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        fieldnames = ["id", "page_name", "status", "url"]
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            for key, value in data.items():
                writer.writerow({"id": key, "page_name": value, "status": "0", "url": ""})

        self.logger.info("CSV task list create ki gayi %s se", csv_path)
        return csv_path

    def _read_tasks(self, csv_path: Path):
        with open(csv_path, "r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            rows = list(reader)
            fieldnames = reader.fieldnames or ["id", "page_name", "status", "url"]

        # ensure url column exists even in older CSVs
        if "url" not in fieldnames:
            fieldnames = ["id", "page_name", "status", "url"]
            for row in rows:
                row.setdefault("url", "")
            self._write_tasks(csv_path, rows, fieldnames)

        return rows, fieldnames

    def _write_tasks(self, csv_path: Path, rows, fieldnames):
        with open(csv_path, "w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _get_next_pending_task(self, csv_path: Path):
        rows, fieldnames = self._read_tasks(csv_path)
        for index, row in enumerate(rows):
            status = row.get("status", "0").strip()
            if status == "0":
                return row, rows, index, fieldnames
        return None, rows, None, fieldnames

    def _prepare_prompts(self, page_name: str):
        prompt1, prompt2, prompt3 = self.load_prompts()
        if not any([prompt1, prompt2, prompt3]):
            raise ValueError("Prompt templates missing in prompts.json")
        return (
            prompt1.format(page_name=page_name),
            prompt2.format(page_name=page_name),
            prompt3.format(page_name=page_name)
        )

    def _process_page(self, page_name: str, send_button_locator, download_link_xpath) -> tuple[bool, str]:
        try:
            prompt1, prompt2, prompt3 = self._prepare_prompts(page_name)
        except Exception as exc:
            self.logger.error("Prompt prepare faild for %s: %s", page_name, exc)
            return False, ""

        success = True
        generated_url = ""

        try:
            self.create_new_branch_switch_driver()
            sleep(2)
            self.type_text(By.XPATH, '//*[@id="prompt-textarea"]', prompt1)
            sleep(2)
            self.check_response_complete(send_button_locator)
            sleep(2)
            self.type_text(By.XPATH, '//*[@id="prompt-textarea"]', prompt2)
            sleep(2)
            self.check_response_complete(send_button_locator)
            sleep(2)
            self.scroll_until_link_present(download_link_xpath)
            sleep(2)
            success = self.download_file() and success
            sleep(2)
            self.type_text(By.XPATH, '//*[@id="prompt-textarea"]', prompt3)
            sleep(2)
            self.check_response_complete(send_button_locator)
            sleep(2)
            self.scroll_until_link_present(download_link_xpath)
            sleep(2)
            success = self.download_file() and success
            sleep(2)
            try:
                generated_url = self.driver.current_url
            except Exception:
                generated_url = ""
        except Exception as exc:
            success = False
            self.logger.error("Processing faild for %s: %s", page_name, exc)
        finally:
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.old_tab1)
            except Exception:
                pass

        return success, generated_url
    
    def main(self):
        """Is function me baki sare funtion call kiye hai loop ke satha me yhi branch create, text type, Respose wait, Scroll or file download ka function call kiye hai or last me driver ko vapas main chat par switch kiya hai."""
        download_link_xpath = '//a[contains(normalize-space(.), "Download")]'
        send_button_locator = (By.XPATH, '//button[@aria-label="Stop streaming"]')
        csv_path = self._ensure_tasks_csv()

        while True:
            task, rows, index, fieldnames = self._get_next_pending_task(csv_path)
            if task is None:
                self.logger.info("Koi pending page nahi bacha, loop stop.")
                break

            page_name = task.get("page_name") or task.get("name") or task.get("title")
            if not page_name:
                self.logger.error("Task me page name missing hai, status failed mark kar rahe hain.")
                if index is not None:
                    rows[index]["status"] = "2"
                    self._write_tasks(csv_path, rows, fieldnames)
                continue

            self.logger.info("Processing page: %s", page_name)
            success, generated_url = self._process_page(page_name, send_button_locator, download_link_xpath)

            if index is not None:
                rows[index]["status"] = "1" if success else "2"
                if generated_url:
                    rows[index]["url"] = generated_url
                self._write_tasks(csv_path, rows, fieldnames)
            else:
                self.logger.warning("Index missing for task %s, CSV update skip.", page_name)

    def close(self):
        "ye function browser ko close karta hai."
        self.logger.info("Closing browser")
        self.driver.quit()   # Browser ko close karta hai

if __name__ == "__main__":
    url = CHAT_SESSION_URL
    obj = ChatGptAutomation(profile_path="C:/Users/Root/AppData/Local/Google/Chrome/User Data/profile for selenium", profile_name="Profile 2")
    obj.open_url(url)
    sleep(2)
    obj.main()
    sleep(60)
    obj.close()


"""Ise pahli bar run karne par chat gpt me login karna parega fir next time without login ke kam chal jayega. url variable me chat ka url dalna hoga jise aap open karna chahte hai. load_page_promt() function me filename variable me json file ka path lagana hoga jisme web pages ke name honge dict format me."""

"""IMPORTANT: Page ke scroll hone ke bad agar end me agar download link screen par visible nhi hai extra content ki vajah se to file download nhi hogi, kyonki link par click karne ke liye usaka visible hona jarury hai. Agar extra text aa raha hai to prompt ko modify karna par sakata hai jisase ki response me sirf download link aaye. """
 