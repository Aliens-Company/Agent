import logging
import os
from pathlib import Path
from datetime import datetime
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
from time import sleep

class ChatGptAutomation:
    def __init__(self, profile_path=None, profile_name=None):
        self._setup_logging()
        self.logger.info("Initializing GptBot....")

        
        chrome_options = Options()
        self.profile_path = Path(profile_path).expanduser() if profile_path else None

        if self.profile_path:
            if not self.profile_path.exists():
                self.logger.warning(
                    "Profile path %s not found. Creating it for Selenium session.",
                    self.profile_path
                )
                self.profile_path.mkdir(parents=True, exist_ok=True)
            if not self._cleanup_chrome_locks(self.profile_path):
                self.profile_path = self._create_fresh_profile_dir(self.profile_path)
            chrome_options.add_argument(f"--user-data-dir={self.profile_path}")
            self.logger.info("Using Chrome profile directory: %s", self.profile_path)
        else:
            self.logger.info("No Chrome profile path configured. Using a temporary profile.")
        
        if profile_name:
            chrome_options.add_argument(f"--profile-directory={profile_name}")

        chrome_options.add_argument("--no-sandbox")                                       # security sandbox disable.
        chrome_options.add_argument("--disable-dev-shm-usage")                            # chrome ko /dev/shm(shared memory) use karne se rokata hai.
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")      # chrome ke automation detection flag ko hide karta hai.
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])  # chrome ke upar jo banner aata hai use remove karta hai.
        chrome_options.add_experimental_option('useAutomationExtension', False)           # chrome ki automation extention ko disable karta hai.
        chrome_options.add_argument('--no-first-run')                                     # chrome ka first run setup remove karta hai.
        chrome_options.add_argument('--no-default-browser-check')                         # chrome popup (make chrome your defualt browser)
        chrome_options.add_argument(                                                      # ye chrome browser ka user agent string manualy set karta hai.
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            "AppleWebKit/537.36 (KHTML, like Gecko)"
            "Chrome/143.0.0.0 Safari/537.36"
        )

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.maximize_window()                                                       # window size ko maximize karta hai.
        self.action = ActionChains(self.driver)
        self.wait = WebDriverWait(self.driver, 40)

    def _setup_logging(self):   # ye ek private function hai logging setup ke liye.
        logging.basicConfig(  # logging system configure ho raha hai.
            level=logging.DEBUG,    # sabhi type ke log capture honge(DEBUG,ERROR,INFO,CRITICAL,WARNING).
            format='%(asctime)s - %(levelname)s - %(message)s',  # log ka look dicide karta hai.
            handlers=[  # handlers batate hai log kaha kaha jana chahiye.
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

    def check_response_complete(self, send_button_locator):
        """Ye function first prompt ke send karne ke bad continuesly send promt button ko check karta hai ki DOM se gayab huaa ya nhi ager gayab huaa to isase next function call hoga or second prompte send ho jayega."""
        self.logger.info("Checking respose button")
        try:
            self.wait.until(
                Ec.invisibility_of_element(send_button_locator)
            )
        except Exception as e:
            print(f"An Error when checking response button {e}")
            self.logger.error(f"Faild to check button invisibility {e}")

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

        raise TimeoutError("Target link not found after scrolling.")

    def download_file(self):
        """Ye function file download link par click karta hai or file download karta hai."""
        locator_type = By.XPATH
        locator = '//a[contains(normalize-space(.), "Download")]'
        self.logger.info("Clicking on download file element.")
        try: 
            element = self.wait.until(Ec.visibility_of_element_located((locator_type, locator)))
            self.action.move_to_element(element)\
            .pause(0.3)\
            .click()\
            .perform()
            sleep(5)
        
        except Exception as e:
            self.logger.error(f"Faild to download {e}")
  
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
            filename = os.environ.get("PROMPTS_FILE", "todo.json")
            file_path = Path(filename)
            if not file_path.is_absolute():
                base_dir = Path(__file__).resolve().parent
                file_path = base_dir / file_path

            if not file_path.exists():
                sample_pages = {
                    "home": "Home Page",
                    "about": "About",
                    "contact": "Contact"
                }
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(json.dumps(sample_pages, indent=2), encoding="utf-8")
                self.logger.warning(
                    "Prompt file %s missing. A sample template has been created. Update it with your pages.",
                    file_path
                )

            with open(file_path, "r", encoding="utf-8") as file:
                json_text = json.load(file)

            for page_name in json_text.values():
                yield self.generate_page_prompts(page_name)
        
        except Exception as e:
            print(f"An Error occured when process prompts {e}")

    def generate_page_prompts(self, page_name:str) -> dict:
        """ye function prompt ko loop me chalane ke liye banaya hai"""

        if page_name:
            prompt1 = f"Webpage : {page_name}  is webpage ka complete plan do extra detail k saath jo ki meri website k design ko Enterprise Grade  ka bna de "
            prompt2 =  f"Webpage : {page_name}  ok to ab is planning ke hisab se download hone layak file me code likh k do download option ke sath without extra detail AliensStyle and Enterprise Grade ko dhyan me rakhte hue, yeh bhi dhyan rakhna hai k yeh  Aliens School ki website ke baaki pages sy milta julta ho or sath me onefile bana kar do download hone layak AliensStyle  Enterprise Grade Design  CleanCode  Premium Design "

            return {"1": prompt1, "2": prompt2}
        return {}
    
    def main(self):
        """Is function me baki sare funtion call kiye hai loop ke satha me yhi branch create, text type, Respose wait, Scroll or file download ka function call kiye hai or last me driver ko vapas main chat par switch kiya hai."""
        locator = By.XPATH
        text_area_xpath = '//*[@id="prompt-textarea"]' 
        download_link_xpath = '//a[contains(normalize-space(.), "Download")]'
        send_button_locator = (By.CSS_SELECTOR, "button.composer-submit-button")
        try:
            for prompts in self.load_page_prompt():
                prompt1 = prompts.get("1", "")
                prompt2 = prompts.get("2", "")
                self.create_new_branch_switch_driver()
                sleep(2)
                self.type_text(locator, text_area_xpath, prompt1)
                sleep(2)
                self.check_response_complete(send_button_locator)
                sleep(2)
                self.type_text(locator, text_area_xpath, prompt2)
                sleep(2)
                self.scroll_until_link_present(download_link_xpath)
                sleep(6)
                self.download_file()
                sleep(10)
                self.driver.switch_to.window(self.old_tab1)  #  driver ko vapas main chat wali tab pe le jata hai.
        except Exception as e:
            print(f"An error occured {e}")

    def close(self):
        "ye function browser ko close karta hai."
        self.logger.info("Closing browser")
        self.driver.quit()   # Browser ko close karta hai

    def _cleanup_chrome_locks(self, profile_root: Path) -> bool:
        """Remove stale Chrome lock files that can prevent new sessions."""
        lock_names = ("lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket")
        for lock_name in lock_names:
            lock_path = profile_root / lock_name
            if lock_path.exists():
                try:
                    lock_path.unlink()
                    self.logger.info("Removed stale Chrome lock: %s", lock_path)
                except OSError as exc:
                    self.logger.warning("Unable to remove Chrome lock %s: %s", lock_path, exc)
                    return False
        return True

    def _create_fresh_profile_dir(self, base_path: Path) -> Path:
        """Create a new profile dir when the existing one is still locked."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        fresh_dir = base_path.parent / f"{base_path.name}-session-{timestamp}"
        fresh_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info("Falling back to fresh Chrome profile directory: %s", fresh_dir)
        return fresh_dir

def _resolve_chrome_profile() -> tuple[str | None, str | None]:
    """Determine Chrome profile path/name using env vars or sensible defaults."""
    env_path = os.environ.get("CHROME_PROFILE_ROOT")
    env_name = os.environ.get("CHROME_PROFILE_NAME")

    if env_path:
        return env_path, env_name

    workspace_profile = Path(__file__).resolve().parent / "temp" / "chrome-profile"
    return str(workspace_profile), env_name

if __name__ == "__main__":
    url = "https://chatgpt.com/c/69476401-05d0-8320-98c0-754b51e34419"
    profile_path, profile_name = _resolve_chrome_profile()
    obj = ChatGptAutomation(profile_path=profile_path, profile_name=profile_name)
    obj.open_url(url)
    sleep(2)
    obj.main()
    sleep(60)
    obj.close()


"""Ise pahli bar run karne par chat gpt me login karna parega fir next time without login ke kam chal jayega. url variable me chat ka url dalna hoga jise aap open karna chahte hai. load_page_promt() function me filename variable me json file ka path lagana hoga jisme web pages ke name honge dict format me."""

"""IMPORTANT: Page ke scroll hone ke bad agar end me agar download link screen par visible nhi hai extra content ki vajah se to file download nhi hogi, kyonki link par click karne ke liye usaka visible hona jarury hai. Agar extra text aa raha hai to prompt ko modify karna par sakata hai jisase ki response me sirf download link aaye. """

 