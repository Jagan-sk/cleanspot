import io

from PIL import Image

from app.auth import create_access_token
from app.models import User

# Real signed JWTs for the seeded demo accounts.
# Fresh-DB seed order -> ids: citizen=1, officer=2, admin=3,
# officer_zone1=4, officer_zone2=5, officer_zone3=6, officer_zone4=7
CITIZEN = {"Authorization": f"Bearer {create_access_token(User(id=1, role='citizen'))}"}
OFFICER = {"Authorization": f"Bearer {create_access_token(User(id=2, role='officer'))}"}  # zone1
ADMIN = {"Authorization": f"Bearer {create_access_token(User(id=3, role='admin'))}"}
OFFICER_Z1 = {"Authorization": f"Bearer {create_access_token(User(id=4, role='officer'))}"}
OFFICER_Z2 = {"Authorization": f"Bearer {create_access_token(User(id=5, role='officer'))}"}
OFFICER_Z3 = {"Authorization": f"Bearer {create_access_token(User(id=6, role='officer'))}"}
OFFICER_Z4 = {"Authorization": f"Bearer {create_access_token(User(id=7, role='officer'))}"}

# centre of sample zone1 - the default test location so officer flows work
ZONE1_LAT, ZONE1_LON = 12.93, 77.58


def make_image_bytes(color=(20, 180, 90), size=(80, 80)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return buf.getvalue()


def image_file(name="report.jpg", color=(20, 180, 90)) -> dict:
    return {"image": (name, make_image_bytes(color), "image/jpeg")}


def submit(client, lat=ZONE1_LAT, lon=ZONE1_LON, headers=CITIZEN, color=(20, 180, 90), **extra):
    data = {"latitude": str(lat), "longitude": str(lon), **extra}
    return client.post("/api/citizen/submit", data=data, files=image_file(color=color), headers=headers)


def login(client, username: str, password: str):
    return client.post("/api/auth/login", json={"username": username, "password": password})
