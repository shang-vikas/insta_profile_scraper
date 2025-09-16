import bcrypt

password = b"my_secret_password"  # your real password
hashed = bcrypt.hashpw(password, bcrypt.gensalt())
print(hashed.decode())

