import logging
import csv
import random
import shutil
import queue
import threading
from pathlib import Path
from typing import Optional
from datetime import datetime
from openai import AzureOpenAI
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
try:
    import tkinter as tk
except Exception:  # pragma: no cover - tkinter optional
    tk = None
import json
from time import sleep, time

from config import (
    CHAT_SESSION_URL,
    AZURE_API_KEY,
    AZURE_ENDPOINT,
    AZURE_API_VERSION,
    LLM_DEPLOYMENT,
    FLOW_CONTROL,
)


BASE_DIR = Path(__file__).resolve().parent
ALIEN_ROOT = BASE_DIR.parent / ".Alien"
PROMPT_DIR = ALIEN_ROOT / "Prompt"
PROMPT_ARCHIVE_DIR = ALIEN_ROOT / "Prompts"
TODO_DIR = ALIEN_ROOT / "ToDo"
LOG_DIR = ALIEN_ROOT / "Logs"
TODO_CSV_PATH = TODO_DIR / "todo.csv"
LEGACY_TODO_CSV_PATH = BASE_DIR / "todo.csv"
PROMPT_FILE_MAP = {
    "1": PROMPT_DIR / "Prompt1.md",
    "2": PROMPT_DIR / "Prompt2.md",
    "3": PROMPT_DIR / "Prompt3.md",
}
PROMPT_CSV_CANDIDATES = [PROMPT_DIR / "prompts.csv", BASE_DIR / "prompts.csv"]
TODO_SEED_CANDIDATES = [
    TODO_DIR / "todo.json",
    PROMPT_DIR / "aliens_school_webpages.json",
    BASE_DIR / "todo.json",
    BASE_DIR / "aliens_school_webpages.json",
]
WEBPAGE_JSON_CANDIDATES = [
    PROMPT_DIR / "aliens_school_webpages.json",
    BASE_DIR / "aliens_school_webpages.json",
]
LOG_FILE_PATH = LOG_DIR / "GptBot.log"
TASK_FIELDNAMES = [
    "id",
    "page_name",
    "planning",
    "code_generate",
    "code_download",
    "docs_generate",
    "docs_download",
    "complete_status",
    "url",
]
STEP_STATUS_COLUMNS = [
    "planning",
    "code_generate",
    "code_download",
    "docs_generate",
    "docs_download",
]


class SystemSnackbar:
    """Lightweight top-right overlay to show automation status."""

    def __init__(self, initial_message: str = "Automation warming up..."):
        self.initial_message = initial_message
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._enabled = tk is not None
        if self._enabled:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def _run(self):
        try:
            self._root = tk.Tk()
        except Exception:
            self._enabled = False
            return

        self._root.overrideredirect(True)
        self._root.lift()
        self._root.attributes("-topmost", True)
        self._root.configure(bg="#000000")

        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        width = max(300, int(screen_h * 0.5))
        height = 77
        x_pos = max(0, screen_w - width - 111)
        y_pos = 25
        self._root.geometry(f"{width}x{height}+{x_pos}+{y_pos}")

        self._label = tk.Label(
            self._root,
            text=self.initial_message,
            bg="#000000",
            fg="#ffffff",
            font=("Segoe UI", 9),
            anchor="w",
            padx=18,
            pady=10,
        )
        self._label.pack(fill="both", expand=True)

        self._poll_queue()
        self._root.mainloop()

    def _poll_queue(self):
        if self._stop_event.is_set():
            try:
                self._root.destroy()
            except Exception:
                pass
            return

        try:
            while True:
                message = self._queue.get_nowait()
                self._label.config(text=message)
        except queue.Empty:
            pass

        self._root.after(150, self._poll_queue)

    def show(self, message: str):
        if not self._enabled or not message:
            return
        self._queue.put(message)

    def close(self):
        if not self._enabled:
            return
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)


class SnackbarLogHandler(logging.Handler):
    """Routes log records to the on-screen snackbar for quick visibility."""

    def __init__(self, update_callback):
        super().__init__(level=logging.INFO)
        self.update_callback = update_callback
        self.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    def emit(self, record):
        try:
            message = self.format(record)
            self.update_callback(message[:200])  # snackbar me concise text
        except Exception:
            pass

class ChatGptAutomation:
    def __init__(self, profile_path=None, profile_name=None):
        self.prompt_cache = {}
        self.todo_csv_path = TODO_CSV_PATH
        self.legacy_todo_csv_path = LEGACY_TODO_CSV_PATH
        self.todo_seed_candidates = TODO_SEED_CANDIDATES
        self.webpage_json_candidates = WEBPAGE_JSON_CANDIDATES
        self.prompt_file_map = PROMPT_FILE_MAP
        self.prompt_csv_candidates = PROMPT_CSV_CANDIDATES
        self.log_path = LOG_FILE_PATH
        self.prompt_archive_dir = PROMPT_ARCHIVE_DIR
        self.typing_delay_range = (0.08, 0.35)
        self.short_pause_range = (1.4, 3.2)
        self.long_pause_range = (4.5, 7.5)
        self.idle_scroll_probability = 0.45
        self.llm_client = None
        self.llm_deployment = LLM_DEPLOYMENT
        self.snackbar = SystemSnackbar("Agent init in progress…")
        self.flow_control = dict(FLOW_CONTROL)
        self._auto_scroll_stop = threading.Event()
        self._auto_scroll_thread: Optional[threading.Thread] = None

        self._setup_logging()
        self.logger.info("Initializing GptBot....")
        self._init_prompt_refiner()

        
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
        self._apply_stealth_patches()
        self.driver.maximize_window()                                                      # window size ko maximize karta hai.
        self.action = ActionChains(self.driver)
        self.wait = WebDriverWait(self.driver, 40)
        self._start_auto_scroll()

    def _setup_logging(self):            # ye ek private function hai logging setup ke liye.
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(             # logging system configure ho raha hai.
            level=logging.DEBUG,         # sabhi type ke log capture honge(DEBUG,ERROR,INFO,CRITICAL,WARNING).
            format='%(asctime)s - %(levelname)s - %(message)s',  # log ka look dicide karta hai.
            handlers=[                   # handlers batate hai log kaha kaha jana chahiye.
                logging.FileHandler(self.log_path, mode="w"),  # Log shared .Alien folder me save hoga taaki Agent dir clean rahe.
                logging.StreamHandler()  # log terminal me show hoga.
            ]
        )
        self.logger = logging.getLogger("WebBot") # Yaha logging object create kiya hai name diya hai WebBot
        try:
            handler = SnackbarLogHandler(self._update_snackbar)
            logging.getLogger().addHandler(handler)
            self.snackbar_handler = handler
        except Exception:
            self.snackbar_handler = None

    def _init_prompt_refiner(self):
        if not all([AZURE_API_KEY, AZURE_ENDPOINT, AZURE_API_VERSION, self.llm_deployment]):
            self.logger.warning("Azure OpenAI credentials incomplete, prompt refiner skip.")
            return

        try:
            self.llm_client = AzureOpenAI(
                api_key=AZURE_API_KEY,
                azure_endpoint=AZURE_ENDPOINT,
                api_version=AZURE_API_VERSION,
            )
            self.logger.info("Prompt refiner ready via Azure OpenAI deployment %s", self.llm_deployment)
        except Exception as exc:
            self.llm_client = None
            self.logger.warning("Prompt refiner init fail: %s", exc)

    def _should_run_step(self, step_id: str) -> bool:
        """Check flow-control flag for the given step."""
        value = self.flow_control.get(step_id, 1)
        try:
            return bool(int(value))
        except (TypeError, ValueError):
            self.logger.debug("Flow flag invalid for %s (value=%s), default run", step_id, value)
            return True

    def _human_pause(self, minimum=None, maximum=None):
        """Har action ke beech human-like random delay add karta hai."""
        low, high = self.short_pause_range
        if minimum is not None:
            low = minimum
        if maximum is not None:
            high = maximum

        if low > high:
            low, high = high, low

        delay = random.uniform(low, high)
        sleep(delay)
        if random.random() < 0.4:
            self._background_mouse_wiggle()
        return delay

    def _random_typing_delay(self):
        return random.uniform(*self.typing_delay_range)

    def _simulate_idle_user_activity(self):
        """Page par halka scroll/idle interaction create karta hai."""
        if random.random() > self.idle_scroll_probability:
            self._background_mouse_wiggle()
            return

        try:
            scroll_distance = random.randint(180, 420) * random.choice([-1, 1])
            self.driver.execute_script("window.scrollBy(0, arguments[0]);", scroll_distance)
            self._human_pause(0.8, 1.6)
            self.driver.execute_script("window.scrollBy(0, arguments[0]);", -scroll_distance + random.randint(-60, 60))
        except Exception as exc:
            self.logger.debug("Idle interaction skip: %s", exc)
        finally:
            self._background_mouse_wiggle()

    def _post_prompt_routine(self):
        self._human_pause(2.2, 4.0)
        self._simulate_idle_user_activity()

    def _update_snackbar(self, message: str):
        try:
            if self.snackbar:
                self.snackbar.show(message)
        except Exception:
            pass

    def _background_mouse_wiggle(self):
        try:
            current_x, current_y = pyautogui.position()
            offset_x = random.randint(-40, 40)
            offset_y = random.randint(-25, 25)
            target_x = max(2, current_x + offset_x)
            target_y = max(2, current_y + offset_y)
            duration = random.uniform(0.2, 0.6)
            pyautogui.moveTo(target_x, target_y, duration=duration)
        except Exception as exc:
            self.logger.debug("Mouse wiggle skip: %s", exc)

    def _auto_scroll_loop(self):
        while not self._auto_scroll_stop.is_set():
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except Exception as exc:
                self.logger.debug("Auto scroll skip: %s", exc)
            if self._auto_scroll_stop.wait(2.0):
                break

    def _start_auto_scroll(self):
        if self._auto_scroll_thread and self._auto_scroll_thread.is_alive():
            return
        self._auto_scroll_stop.clear()
        self._auto_scroll_thread = threading.Thread(target=self._auto_scroll_loop, daemon=True)
        self._auto_scroll_thread.start()

    def _stop_auto_scroll(self):
        if not self._auto_scroll_thread:
            return
        self._auto_scroll_stop.set()
        self._auto_scroll_thread.join(timeout=2.5)
        self._auto_scroll_thread = None

    def _move_mouse(self, x: float, y: float, jitter: float = 18.0):
        try:
            target_x = x + random.uniform(-jitter, jitter)
            target_y = y + random.uniform(-jitter, jitter)
            duration = random.uniform(0.35, 0.9)
            pyautogui.moveTo(target_x, target_y, duration=duration)
        except Exception as exc:
            self.logger.debug("Mouse move skip: %s", exc)

    def _move_mouse_to_element(self, element: Optional[object]):
        if element is None:
            return

        try:
            coords = self.driver.execute_script(
                "const r = arguments[0].getBoundingClientRect();"
                "const offsetX = window.screenX + (window.outerWidth - window.innerWidth);"
                "const offsetY = window.screenY + (window.outerHeight - window.innerHeight);"
                "return {x: r.left + r.width / 2 + offsetX, y: r.top + r.height / 2 + offsetY};",
                element,
            )
            if coords and "x" in coords and "y" in coords:
                self._move_mouse(coords["x"], coords["y"], jitter=22.0)
        except Exception as exc:
            self.logger.debug("Element mouse move skip: %s", exc)

    def _apply_stealth_patches(self):
        scripts = [
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});",
            "window.navigator.chrome = { runtime: {} };",
            "Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});",
            "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4]});"
        ]

        for script in scripts:
            try:
                self.driver.execute_cdp_cmd(
                    "Page.addScriptToEvaluateOnNewDocument",
                    {"source": script}
                )
            except Exception as exc:
                self.logger.debug("Stealth patch fail: %s", exc)

    def open_url(self, url: str):
        """Ye function url ko open karta hai."""
        self.logger.info(f"Opning Url {url}")
        try:
            self.driver.get(url)
            self._human_pause(5.0, 7.8)
            self._simulate_idle_user_activity()
            self._update_snackbar("Chat session ready")
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
            self._move_mouse_to_element(last_element)

            last_element.send_keys(Keys.ENTER)  # Iske bina element par click nhi ho sakata hai kisi bhi tarike se kyonki element div ke niche hai.
            
        except Exception as e:
            self.logger.error(f"Click faild: {e}")

    def _send_multiline_text(self, element, text: str):
        """Textarea me text paste karte waqt newline ke liye Shift+Enter ka use karta hai."""
        actions = ActionChains(self.driver)
        actions.move_to_element(element).click().pause(self._random_typing_delay())

        if not text:
            actions.send_keys(Keys.ENTER).perform()
            return

        for chunk in text.splitlines(keepends=True):
            cleaned = chunk.rstrip("\r\n")
            if cleaned:
                actions.send_keys(cleaned).pause(self._random_typing_delay())
            if chunk.endswith(("\n", "\r")):
                actions.key_down(Keys.SHIFT).send_keys(Keys.ENTER).key_up(Keys.SHIFT).pause(self._random_typing_delay())

        actions.pause(self._random_typing_delay()).send_keys(Keys.ENTER).perform()

    def type_text(self, locator_type, locator, text: str):
        """Ye funtion input field me text ko fill karta hai or send karta hai."""
        self.logger.info(f"Typing text in element {locator}")
        try:
            element = self.wait.until(Ec.visibility_of_element_located((locator_type, locator)))  # ye function element ka tab tak wait karega jab tak ki element visibile na ho jaye ya timeout tak. until() bar bar funtion call karta hai or check karta  rahata hai.Isme arguments tuple ke form me bheje jate hai.
            self._move_mouse_to_element(element)
            element.click()
            self._human_pause(*self.long_pause_range)
            self._send_multiline_text(element, text)
            self._human_pause()
        
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
                self._background_mouse_wiggle()

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
            self._move_mouse_to_element(last_element)
            self.logger.info("Pausing 5 seconds before download click")
            self._human_pause(5.0, 5.0)
            self.action.move_to_element(last_element)\
            .pause(0.3)\
            .click()\
            .perform()
            self._human_pause(4.5, 6.8)
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
            self._human_pause(4.0, 6.5)
            self.logger.info(f"Clicking element {new_branch_button_selector}")
            branch_button = self.wait.until(Ec.visibility_of_element_located((locator_type, new_branch_button_selector)))
            self._move_mouse_to_element(branch_button)
            branch_button.click()

            new_tabs = self.driver.window_handles

            for tab in new_tabs:
                if tab  not in self.old_tab:
                    self.driver.switch_to.window(tab)  # window() function se driver switch kiya hai new branch ki tab par
                    break
        except Exception as e:
            self.logger.error(f"Click Faild: {e}")
  
    def _find_existing_path(self, candidates):
        for path in candidates:
            if path and Path(path).exists():
                return Path(path)
        return None

    def _read_prompt_file(self, prompt_id: str) -> str:
        if prompt_id in self.prompt_cache:
            return self.prompt_cache[prompt_id]

        prompt_path = self.prompt_file_map.get(prompt_id)
        if prompt_path and prompt_path.exists():
            content = prompt_path.read_text(encoding="utf-8")
            self.prompt_cache[prompt_id] = content
            return content

        self.logger.warning("Prompt file missing: %s", prompt_path)
        self.prompt_cache[prompt_id] = ""
        return ""

    def _load_prompt_markdown(self):
        prompt_list = [self._read_prompt_file(pid) for pid in ("1", "2", "3")]
        if any(prompt_list):
            return tuple(prompt_list)
        return "", "", ""

    def _render_prompt_template(self, template: str, page_name: str):
        if not template:
            return ""

        file_path = page_name or ""
        file_name = Path(file_path).name if file_path else ""
        replacements = {
            "{{FILE_PATH}}": file_path,
            "{{FILE_NAME}}": file_name,
        }

        rendered = template
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)

        try:
            rendered = rendered.format(page_name=page_name)
        except Exception:
            pass

        return rendered

    def _archive_refined_prompt(self, page_name: str, label: str, original: str, refined: str):
        try:
            self.prompt_archive_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            base_name = Path(page_name).name or "unknown"
            safe_name = "".join(
                ch if ch.isalnum() or ch in ("-", "_") else "_"
                for ch in base_name
            ) or "page"
            label = label or "prompt"
            filename = f"{timestamp}_{safe_name}_{label}.md"
            archive_path = self.prompt_archive_dir / filename
            content = (
                f"# Page: {page_name or 'unknown'}\n"
                f"# Prompt Label: {label}\n"
                f"# Timestamp (UTC): {timestamp}\n\n"
                "## Original Prompt\n\n"
                f"{original.strip()}\n\n"
                "## Refined Prompt\n\n"
                f"{refined.strip()}\n"
            )
            archive_path.write_text(content, encoding="utf-8")
            return archive_path
        except Exception as exc:
            self.logger.warning("Prompt archive fail: %s", exc)
        return None

    def _refine_prompt(self, prompt_text: str, page_name: str, label: str) -> str:
        if not prompt_text or not prompt_text.strip():
            return prompt_text
        if self.llm_client is None:
            self.logger.warning("Prompt refiner disabled, using original text for %s", label)
            self._archive_refined_prompt(page_name, label, prompt_text, prompt_text)
            return prompt_text

        instructions_parts = [
            "Rewrite the provided automation prompt in natural Hinglish while preserving its exact intent,",
            "required actions, placeholders, download instructions, and tone.",
            "The new draft must stay concise, enterprise-grade, and produce the same output when sent to ChatGPT.",
            "Do not add or remove requirements. Return only the rewritten prompt text.",
        ]
        instructions = " ".join(instructions_parts)

        user_payload = (
            f"Target page/file: {page_name or 'unknown'}\n"
            "Original prompt:\n"
            f"{prompt_text}\n\n"
            "Rewrite it now."
        )

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_deployment,
                temperature=0.35,
                max_tokens=min(600, max(200, int(len(prompt_text) * 1.3))),
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": user_payload},
                ],
            )

            refined = (response.choices[0].message.content or "").strip()
            if refined:
                archive_path = self._archive_refined_prompt(page_name, label, prompt_text, refined)
                if archive_path:
                    self.logger.info(
                        "Prompt refined via Azure OpenAI (%s) saved to %s",
                        label,
                        archive_path,
                    )
                else:
                    self.logger.info("Prompt refined via Azure OpenAI (%s) [archive skipped]", label)
                return refined
        except Exception as exc:
            self.logger.warning("Prompt refine skip (%s/%s): %s", page_name, label, exc)

        # Even on failure archive original for forensic visibility
        self._archive_refined_prompt(page_name, label, prompt_text, prompt_text)
        return prompt_text
        
        
    def load_page_prompt(self):
        """Ye function json file se ek ek karke promts ko utha raha hai or unhe generate kar raha gtp ko dene ke liye or prompts ko return kar raha hai."""
        try:
            filename = self._find_existing_path(self.webpage_json_candidates)
            if not filename:
                raise FileNotFoundError("Webpage seed list missing in .Alien/Prompt")
            with open(filename, "r", encoding="utf-8") as file:
                data = file.read()
                json_text = json.loads(data)  # loads() function json string ko python data me convert karta hai.

            for page_name in json_text.values():
                yield self.generate_page_prompts(page_name)  # yeild function ko generator bana deta hai.
        
        except Exception as e:
            print(f"An Error occured when process prompts {e}")
        
    def load_prompts(self):
        markdown_prompts = self._load_prompt_markdown()
        if any(markdown_prompts):
            return markdown_prompts

        csv_path = self._find_existing_path(self.prompt_csv_candidates)
        if not csv_path:
            self.logger.error("Prompt templates missing. Please add markdown prompts in %s", PROMPT_DIR)
            return "", "", ""

        try:
            with open(csv_path, "r", encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file)
                prompts = {
                    (row.get("id") or "").strip(): row.get("prompt", "")
                    for row in reader
                }
        except FileNotFoundError:
            self.logger.error("Prompts CSV %s missing hai", csv_path)
            return "", "", ""
        except Exception as exc:
            self.logger.error("Prompts CSV read faild (%s): %s", csv_path, exc)
            return "", "", ""

        return (
            prompts.get("1", ""),
            prompts.get("2", ""),
            prompts.get("3", "")
        )
        
    def load_webpage_data(self):
        try:
            filename = self._find_existing_path(self.webpage_json_candidates)
            if not filename:
                raise FileNotFoundError("Webpage seed list missing in .Alien/Prompt")
            with open(filename, "r", encoding="utf-8") as file:
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

    def _ensure_tasks_csv(self) -> Path:
        csv_path = self.todo_csv_path
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        if not csv_path.exists():
            if self.legacy_todo_csv_path.exists():
                shutil.copy2(self.legacy_todo_csv_path, csv_path)
                self.logger.info("Legacy todo CSV migrated to %s", csv_path)
            else:
                self._seed_tasks_csv(csv_path)

        # Normalize legacy structures into the expanded schema
        self._normalize_task_file(csv_path)
        return csv_path

    def _seed_tasks_csv(self, csv_path: Path):
        seed_json = self._find_existing_path(self.todo_seed_candidates)
        if not seed_json:
            raise FileNotFoundError(
                "Todo CSV missing and no seed list found in .Alien/ToDo or .Alien/Prompt"
            )

        with open(seed_json, "r", encoding="utf-8") as file:
            data = json.load(file)

        with open(csv_path, "w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=TASK_FIELDNAMES)
            writer.writeheader()

            items = data.items() if isinstance(data, dict) else enumerate(data, start=1)
            for key, value in items:
                if isinstance(value, dict):
                    page_name = value.get("page_name") or value.get("name") or value.get("title") or ""
                else:
                    page_name = value
                writer.writerow(self._build_task_row(key, page_name))

        self.logger.info("CSV task list create ki gayi %s se", csv_path)

    def _normalize_task_file(self, csv_path: Path):
        rows, _ = self._read_tasks(csv_path)
        # _read_tasks already rewrites if needed, so no-op here beyond ensuring read succeeds
        return rows

    def _build_task_row(self, identifier, page_name, url: str = ""):
        row = {column: "0" for column in TASK_FIELDNAMES}
        row["id"] = str(identifier)
        row["page_name"] = page_name or ""
        row["url"] = url or ""
        return row

    def _normalize_task_row(self, row: dict, fallback_id: int) -> dict:
        normalized = {column: "0" for column in TASK_FIELDNAMES}
        identifier = (row.get("id") or "").strip()
        if not identifier:
            identifier = str(fallback_id)
        normalized["id"] = identifier
        normalized["page_name"] = (row.get("page_name") or "").strip()
        normalized["url"] = (row.get("url") or "").strip()

        # Map legacy status/complete indicators
        legacy_status = row.get("complete_status")
        if legacy_status is None:
            legacy_status = row.get("status")
        if legacy_status is not None:
            normalized["complete_status"] = "1" if str(legacy_status).strip() == "1" else "0"

        for column in STEP_STATUS_COLUMNS:
            value = row.get(column)
            if value is not None and str(value).strip() == "1":
                normalized[column] = "1"

        return normalized

    def _read_tasks(self, csv_path: Path):
        with open(csv_path, "r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            raw_rows = list(reader)
            original_fieldnames = reader.fieldnames or []

        needs_write = original_fieldnames != TASK_FIELDNAMES
        rows = []
        for idx, raw in enumerate(raw_rows, start=1):
            normalized = self._normalize_task_row(raw, idx)
            rows.append(normalized)
            if not needs_write:
                for column in TASK_FIELDNAMES:
                    original_value = (raw.get(column) or "").strip()
                    if original_value != normalized[column]:
                        needs_write = True
                        break
                if not needs_write:
                    extra_keys = set(raw.keys()) - set(TASK_FIELDNAMES)
                    if extra_keys:
                        needs_write = True

        if needs_write:
            self._write_tasks(csv_path, rows, TASK_FIELDNAMES)

        return rows, TASK_FIELDNAMES

    def _write_tasks(self, csv_path: Path, rows, fieldnames=None):
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        active_fields = fieldnames or TASK_FIELDNAMES
        with open(csv_path, "w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=active_fields)
            writer.writeheader()
            writer.writerows(rows)

    def _get_next_pending_task(self, csv_path: Path):
        rows, fieldnames = self._read_tasks(csv_path)
        for index, row in enumerate(rows):
            status = row.get("complete_status") or row.get("status") or "0"
            if status.strip() == "0":
                return row, rows, index, fieldnames
        return None, rows, None, fieldnames

    def _prepare_prompts(self, page_name: str):
        prompt1, prompt2, prompt3 = self.load_prompts()
        if not any([prompt1, prompt2, prompt3]):
            raise ValueError("Prompt templates missing in .Alien/Prompt")
        rendered = [
            self._render_prompt_template(prompt1, page_name),
            self._render_prompt_template(prompt2, page_name),
            self._render_prompt_template(prompt3, page_name),
        ]
        labels = ["planning", "build", "doc"]
        refined = [self._refine_prompt(text, page_name, labels[idx]) for idx, text in enumerate(rendered)]
        return tuple(refined)

    def _process_page(self, page_name: str, send_button_locator, download_link_xpath) -> tuple[bool, str, dict]:
        try:
            prompt1, prompt2, prompt3 = self._prepare_prompts(page_name)
            self._update_snackbar(f"Ready: {page_name} plan prompt")
        except Exception as exc:
            self.logger.error("Prompt prepare faild for %s: %s", page_name, exc)
            return False, "", {column: "0" for column in STEP_STATUS_COLUMNS + ["complete_status"]}

        success = True
        generated_url = ""
        step_status = {column: "0" for column in STEP_STATUS_COLUMNS}
        step_status["complete_status"] = "0"

        try:
            self.create_new_branch_switch_driver()
            self._human_pause(2.4, 4.6)
            if self._should_run_step("prompt1"):
                self._update_snackbar(f"{page_name}: Sending plan")
                self.type_text(By.XPATH, '//*[@id="prompt-textarea"]', prompt1)
                self._post_prompt_routine()
                self.check_response_complete(send_button_locator)
                self._human_pause(2.0, 3.6)
                step_status["planning"] = "1"
            else:
                self.logger.info("Prompt1 bypassed for %s", page_name)
                self._update_snackbar(f"{page_name}: Prompt1 bypassed")

            if self._should_run_step("prompt2"):
                self._update_snackbar(f"{page_name}: Requesting build")
                self.type_text(By.XPATH, '//*[@id="prompt-textarea"]', prompt2)
                self._post_prompt_routine()
                self.check_response_complete(send_button_locator)
                self._human_pause(2.0, 3.6)
                step_status["code_generate"] = "1"
            else:
                self.logger.info("Prompt2 bypassed for %s", page_name)
                self._update_snackbar(f"{page_name}: Prompt2 bypassed")

            if self._should_run_step("download1"):
                self._update_snackbar(f"{page_name}: Download prep")
                self.scroll_until_link_present(download_link_xpath)
                self._human_pause(1.8, 3.4)
                download_success = self.download_file()
                step_status["code_download"] = "1" if download_success else "0"
                success = download_success and success
                self._human_pause(2.7, 4.5)
            else:
                self.logger.info("Download1 bypassed for %s", page_name)
                self._update_snackbar(f"{page_name}: Download1 bypassed")

            if self._should_run_step("prompt3"):
                self._update_snackbar(f"{page_name}: Final doc")
                self.type_text(By.XPATH, '//*[@id="prompt-textarea"]', prompt3)
                self._post_prompt_routine()
                self.check_response_complete(send_button_locator)
                self._human_pause(2.0, 3.6)
                step_status["docs_generate"] = "1"
            else:
                self.logger.info("Prompt3 bypassed for %s", page_name)
                self._update_snackbar(f"{page_name}: Prompt3 bypassed")

            if self._should_run_step("download2"):
                self.scroll_until_link_present(download_link_xpath)
                self._human_pause(1.8, 3.4)
                download_success = self.download_file()
                step_status["docs_download"] = "1" if download_success else "0"
                success = download_success and success
                self._human_pause(2.7, 4.5)
            else:
                self.logger.info("Download2 bypassed for %s", page_name)
                self._update_snackbar(f"{page_name}: Download2 bypassed")
            try:
                generated_url = self.driver.current_url
            except Exception:
                generated_url = ""
        except Exception as exc:
            success = False
            self.logger.error("Processing faild for %s: %s", page_name, exc)
            self._update_snackbar(f"{page_name}: Error, see logs")
        finally:
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.close()
                    self.driver.switch_to.window(self.old_tab1)
            except Exception:
                pass

        if success:
            self._update_snackbar(f"{page_name}: Completed ✓")
        else:
            self._update_snackbar(f"{page_name}: Failed ✕")
        step_status["complete_status"] = "1" if success else "0"
        return success, generated_url, step_status
    
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
                    rows[index]["complete_status"] = "0"
                    self._write_tasks(csv_path, rows, fieldnames)
                continue

            self.logger.info("Processing page: %s", page_name)
            success, generated_url, step_status = self._process_page(page_name, send_button_locator, download_link_xpath)

            if index is not None:
                for column in STEP_STATUS_COLUMNS:
                    rows[index][column] = step_status.get(column, rows[index].get(column, "0"))
                rows[index]["complete_status"] = step_status.get("complete_status", "1" if success else "0")
                if generated_url:
                    rows[index]["url"] = generated_url
                self._write_tasks(csv_path, rows, fieldnames)
            else:
                self.logger.warning("Index missing for task %s, CSV update skip.", page_name)

    def close(self):
        "ye function browser ko close karta hai."
        self.logger.info("Closing browser")
        self._stop_auto_scroll()
        self.driver.quit()   # Browser ko close karta hai
        if hasattr(self, "snackbar") and self.snackbar:
            self.snackbar.close()
        if getattr(self, "snackbar_handler", None):
            logging.getLogger().removeHandler(self.snackbar_handler)

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
 