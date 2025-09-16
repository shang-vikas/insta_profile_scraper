import pickle
from selenium import webdriver

driver = webdriver.Chrome()
driver.get("https://www.instagram.com/")  # Must visit domain first

cookies = pickle.load(open("cookies.pkl", "rb"))
for cookie in cookies:
    # Selenium expects 'expiry' to be int if present
    if 'expiry' in cookie and isinstance(cookie['expiry'], float):
        cookie['expiry'] = int(cookie['expiry'])
    driver.add_cookie(cookie)

driver.refresh()  # Apply cookies
print("✅ Logged in using cookies")
input("Press Enter to continue...")
