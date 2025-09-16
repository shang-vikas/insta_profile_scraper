import pickle
from time import time
from selenium import webdriver

driver = webdriver.Chrome()
driver.get("https://www.instagram.com/accounts/login/")

# 🔑 You log in manually in the browser window
input("👉 After logging in successfully, press Enter here...")

# Save cookies
pickle.dump(driver.get_cookies(), open(f"cookies_{time.time()}.pkl", "wb"))
print("✅ Cookies saved to cookies.pkl")

