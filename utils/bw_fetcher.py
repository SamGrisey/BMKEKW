# pylint: disable=missing-module-docstring, missing-function-docstring, missing-class-docstring
import typing as t
from time import sleep
from threading import Thread
from selenium_stealth import stealth
import undetected_chromedriver as uc
from undetected_chromedriver import Chrome
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from utils.db_utils import DBManager


GRECAPTCHA_TOKEN = "09ABpmNwIkOBcSAVYbWrvJ3C5Zu2RJJEbktvAKEN6FqB2zXWcarmgyM9vAiEIhjoBLdqURffE63rLfdNYxyyN2zEcs5g"  # pylint: disable=line-too-long
YIELDS_PER_VIN = 9


class FetchException(Exception):
    pass


def get_selenium_instance() -> Chrome:
    chrome_options = uc.ChromeOptions()
    chrome_options.headless = True
    driver = uc.Chrome(
        options=chrome_options,
        version_main=99,
    )

    stealth(
        driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Linux x86_64",
        webgl_vendor="Google Inc. (Intel)",
        renderer="ANGLE (Intel, Mesa Intel(R) HD Graphics 530 (SKL GT2), "
        + "OpenGL 4.6 (Core Profile) Mesa 21.2.6)",
        fix_hairline=True,
        run_on_insecure_origins=True,
    )

    return driver


class BimmerWorkFetcher:
    def __init__(self):
        self._chrome = get_selenium_instance()
        self._task_progress = 0
        self._current_task = None
        self._task_results = []

    def close(self) -> None:
        self._chrome.close()

    def _fetch_vin(  # pylint: disable=too-many-statements
        self, vin: str
    ) -> t.List[t.Tuple[str, ...]]:
        # bimmer.work is protected by captcha so we need to act like a real person as much as
        # possible. Yields are placed at relatively regulay intervals to report progress back
        # to the parent loop

        # nav to site through google search for more realism
        self._chrome.get("https://www.google.com/search?q=bimmerwork")
        site_link = WebDriverWait(self._chrome, 10).until(
            lambda x: x.find_element(
                by=By.XPATH, value="//a[@href='https://bimmer.work/']"
            )
        )
        sleep(2)
        yield []
        action = ActionChains(self._chrome)
        action.move_to_element(site_link).click().perform()

        # set captcha token from good session for better reliability
        self._chrome.execute_script(
            "localStorage.setItem('_grecaptcha', arguments[0]);",
            GRECAPTCHA_TOKEN,
        )

        # wait and paste in vin as if im reading the page
        vin_textbox = WebDriverWait(self._chrome, 10).until(
            lambda x: x.find_element_by_name("vin")
        )
        action = ActionChains(self._chrome)
        action.move_to_element(vin_textbox).click().perform()
        sleep(2)
        yield []
        vin_textbox.send_keys(vin)
        sleep(2)
        yield []
        sleep(2)
        yield []
        sleep(2)
        yield []

        # fuck you cookie popup (sometimes it doesnt appear in headless)
        try:
            piece_of_trash = self._chrome.find_element(
                by=By.XPATH, value="//button[@class='cc-nb-reject']"
            )
        except Exception:  # pylint: disable=broad-except
            pass
        else:
            sleep(2)
            yield []
            action = ActionChains(self._chrome)
            action.move_to_element(piece_of_trash).perform()
            sleep(1)
            piece_of_trash.click()
            sleep(1)
            yield []

        # oof the captcha
        captcha_iframe = self._chrome.find_element(
            by=By.XPATH, value="//iframe[@title='reCAPTCHA']"
        )
        action = ActionChains(self._chrome)
        action.move_to_element(captcha_iframe).click().perform()
        sleep(2)
        yield []

        # check if we got rekt by the captcha otherwise submit form
        try:
            self._chrome.find_element(
                by=By.XPATH,
                value="//div[@class='g-recaptcha-bubble-arrow' and "
                "not(ancestor::div[contains(@style,'visibility: hidden')])]",
            )
        except Exception:  # pylint: disable=broad-except
            submit_button = self._chrome.find_element(
                by=By.XPATH, value="//button[@type='submit']"
            )
            action = ActionChains(self._chrome)
            action.move_to_element(submit_button).click().perform()
        else:
            raise FetchException(
                "Got rekt by captcha. Try again later maybe or do manual import"
            )

        # wait through the possible 15 sec timer (or sometimes 2) and grab data or error
        data = []
        data_table_elements = WebDriverWait(self._chrome, 35).until(
            lambda x: x.find_elements(
                by=By.XPATH,
                value="//table[@class='table table-striped table-condensed']",
            )
            or x.find_elements(
                by=By.XPATH,
                value="//center[text() = 'Something went wrong, please try again.']",
            )
        )

        # Raise error if vin wasnt found, else pull data from tables
        if data_table_elements[0].text == "Something went wrong, please try again.":
            raise FetchException("VIN not found.")
        for table in data_table_elements:
            rows = table.find_elements(by=By.XPATH, value=".//tr")
            data.extend(
                [
                    (
                        r.find_element(by=By.XPATH, value=".//th").get_attribute(
                            "textContent"
                        ),
                        r.find_element(by=By.XPATH, value=".//td").get_attribute(
                            "textContent"
                        ),
                    )
                    for r in rows
                ]
            )
        yield data

    def start_import_task(self, vin_list: t.List[str]) -> None:
        if len(vin_list) == 0:
            return
        self._current_task = Thread(target=self._import_vins, args=[vin_list])
        self._current_task.start()

    def _import_vins(self, vin_list: t.List[str]) -> None:
        db_ = DBManager()
        progress_per_yield = 100 / (len(vin_list) * YIELDS_PER_VIN)
        self._task_progress = 0
        self._task_results = []
        for idx, vin in enumerate(vin_list):
            try:
                # set up the fetcher as a generator so we can measure progress with
                # greater granularity
                data = []
                for retval in self._fetch_vin(vin):
                    data = retval
                    self._task_progress += progress_per_yield

                import_result = db_.import_vehicle(data)
                self._task_results.append(f"{vin}: {import_result}")
            except FetchException as error:
                self._task_results.append(f"{vin}: {error}")
            except Exception:  # pylint: disable=broad-except
                self._task_results.append(f"{vin}: Generic error")
            self._task_progress = ((idx + 1) / len(vin_list)) * 100
        db_.close()

    def consume_task_results(self) -> t.Optional[t.List[str]]:
        if not self.task_running() or self.task_progress() < 100:
            return None
        self._current_task = None
        return self._task_results

    def task_progress(self) -> int:
        return int(self._task_progress)

    def task_running(self) -> bool:
        return self._current_task is not None
