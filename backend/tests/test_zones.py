"""Phase 2: ward/zone filtering tests (SAMPLE zones from app/config/zones.json)."""
from tests.helpers import ADMIN, CITIZEN, OFFICER, OFFICER_Z2, submit

# centre points of the four sample zones (see app/config/zones.json)
ZONE_CENTERS = {
    "zone1": (12.93, 77.58),
    "zone2": (12.99, 77.58),
    "zone3": (12.93, 77.65),
    "zone4": (12.99, 77.65),
}
COLORS = {"zone1": (11, 12, 13), "zone2": (21, 22, 23), "zone3": (31, 32, 33), "zone4": (41, 42, 43)}


def test_points_inside_each_zone_get_right_zone_id(client):
    for zid, (lat, lon) in ZONE_CENTERS.items():
        r = submit(client, lat=lat, lon=lon, color=COLORS[zid])
        assert r.status_code == 200
        assert r.json()["zone_id"] == zid


def test_point_outside_all_zones_is_unassigned(client):
    r = submit(client, lat=1.0, lon=2.0, color=(9, 9, 9))
    assert r.json()["zone_id"] == "unassigned"


def test_officer_cannot_touch_another_zones_complaint(client):
    cid = submit(client, lat=ZONE_CENTERS["zone2"][0], lon=ZONE_CENTERS["zone2"][1],
                 color=(55, 56, 57)).json()["id"]

    # zone-1 officer: everything 403
    assert client.get(f"/api/citizen/complaints/{cid}", headers=OFFICER).status_code == 403
    assert client.get(f"/municipal/complaints/{cid}", headers=OFFICER).status_code == 403
    assert client.post(f"/municipal/complaints/{cid}/assign", headers=OFFICER).status_code == 403
    assert client.post(f"/municipal/complaints/{cid}/resolve", headers=OFFICER).status_code == 403
    assert client.get(f"/api/photos/{cid}/report", headers=OFFICER).status_code == 403

    # the zone-2 officer can do all of it
    assert client.post(f"/municipal/complaints/{cid}/assign", headers=OFFICER_Z2).status_code == 200
    assert client.get(f"/api/photos/{cid}/report", headers=OFFICER_Z2).status_code == 200


def test_officer_list_only_shows_own_zone(client):
    z1 = submit(client, lat=ZONE_CENTERS["zone1"][0], lon=ZONE_CENTERS["zone1"][1],
                color=(61, 62, 63)).json()["id"]
    z2 = submit(client, lat=ZONE_CENTERS["zone2"][0], lon=ZONE_CENTERS["zone2"][1],
                color=(64, 65, 66)).json()["id"]

    ids = [c["id"] for c in client.get("/municipal/complaints", headers=OFFICER).json()]
    assert z1 in ids
    assert z2 not in ids


def test_unassigned_invisible_to_officers_but_admin_can_filter_it(client):
    cid = submit(client, lat=1.0, lon=2.0, color=(71, 72, 73)).json()["id"]

    officer_ids = [c["id"] for c in client.get("/municipal/complaints", headers=OFFICER).json()]
    assert cid not in officer_ids

    unassigned = [c["id"] for c in client.get("/municipal/complaints?zone=unassigned", headers=ADMIN).json()]
    assert cid in unassigned


def test_admin_sees_all_and_can_filter_by_zone(client):
    z1 = submit(client, lat=ZONE_CENTERS["zone1"][0], lon=ZONE_CENTERS["zone1"][1],
                color=(74, 75, 76)).json()["id"]
    z2 = submit(client, lat=ZONE_CENTERS["zone2"][0], lon=ZONE_CENTERS["zone2"][1],
                color=(77, 78, 79)).json()["id"]

    all_ids = {c["id"] for c in client.get("/municipal/complaints", headers=ADMIN).json()}
    assert {z1, z2} <= all_ids

    only2 = {c["id"] for c in client.get("/municipal/complaints?zone=zone2", headers=ADMIN).json()}
    assert only2 == {z2}

    assert client.get("/municipal/complaints?zone=bogus", headers=ADMIN).status_code == 400


def test_zones_endpoint(client):
    assert client.get("/api/zones").status_code == 401
    for headers in (CITIZEN, OFFICER, ADMIN):
        r = client.get("/api/zones", headers=headers)
        assert r.status_code == 200
        zones = r.json()["zones"]
        assert len(zones) == 4
        assert {z["id"] for z in zones} == {"zone1", "zone2", "zone3", "zone4"}
        # every zone has the fields the frontend needs for rectangles
        for z in zones:
            assert set(z) >= {"id", "name", "min_lat", "max_lat", "min_lng", "max_lng"}


def test_stats_scoped_by_role_and_zone(client):
    submit(client, lat=ZONE_CENTERS["zone1"][0], lon=ZONE_CENTERS["zone1"][1], color=(81, 82, 83))
    submit(client, lat=ZONE_CENTERS["zone2"][0], lon=ZONE_CENTERS["zone2"][1], color=(84, 85, 86))

    # officer: own zone only
    assert client.get("/api/stats", headers=OFFICER).json()["totals"]["total"] == 1
    # admin: everything, or one zone via ?zone=
    assert client.get("/api/stats", headers=ADMIN).json()["totals"]["total"] == 2
    assert client.get("/api/stats?zone=zone2", headers=ADMIN).json()["totals"]["total"] == 1
    assert client.get("/api/stats?zone=bogus", headers=ADMIN).status_code == 400
    # citizen: global view of their world
    assert client.get("/api/stats", headers=CITIZEN).json()["totals"]["total"] == 2


def test_citizens_still_see_only_their_own(client):
    other = submit(client, lat=ZONE_CENTERS["zone1"][0], lon=ZONE_CENTERS["zone1"][1],
                   color=(87, 88, 89)).json()["id"]  # citizen id 1's complaint
    client.post("/api/auth/register", json={"username": "zonebuddy", "password": "long-enough-pw"})
    buddy = client.post("/api/auth/login", json={"username": "zonebuddy", "password": "long-enough-pw"}).json()
    B = {"Authorization": f"Bearer {buddy['token']}"}
    assert other not in [c["id"] for c in client.get("/api/citizen/complaints", headers=B).json()]
    assert client.get(f"/api/citizen/complaints/{other}", headers=B).status_code == 403
