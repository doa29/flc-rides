### Cleaned and De-duplicated Final App Code ###

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import openrouteservice

import gspread
from oauth2client.service_account import ServiceAccountCredentials

def connect_to_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/13BlWU3QY4G0k2GIGt7wppv1_Wsoe_lwPGrbcYa85IDs/edit?usp=sharing")
    return sheet

# -------------------- CONFIG --------------------
st.set_page_config(page_title="FLC Philly Ride Coordinator", layout="wide")

ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjkxMWRjYjBmMWQxNzQ3Mzk5NmEyM2MyYzVkYzNhZmI3IiwiaCI6Im11cm11cjY0In0="
client = openrouteservice.Client(key=ORS_API_KEY)
geolocator = Nominatim(user_agent="flc_philly_ride_app")

# -------------------- SESSION STATE INIT --------------------
def init_session():
    for key, default in {
        'drivers': [],
        'passengers': [],
        'assignments_df': pd.DataFrame(),
        'assignments': {},
        'unassigned': [],
        'destination': None,
        'driver_data': {},
        'map_render': None
    }.items():
        if key not in st.session_state:
            st.session_state[key] = default

init_session()

# -------------------- FUNCTIONS --------------------
def geocode_address(address):
    try:
        location = geolocator.geocode(address)
        return (location.latitude, location.longitude) if location else None
    except:
        return None

def haversine_distance(a, b):
    return geodesic(a, b).miles

def assign_passengers_to_drivers_efficiently(drivers, passengers):
    assignments = {d['name']: [] for d in drivers}
    unassigned = []
    for passenger in passengers:
        closest = sorted([
            (driver, haversine_distance(driver['latlon'], passenger['latlon']))
            for driver in drivers if len(assignments[driver['name']]) < driver['seats']
        ], key=lambda x: x[1])
        if closest:
            assignments[closest[0][0]['name']].append(passenger)
        else:
            unassigned.append(passenger)
    return assignments, unassigned

def get_route(coordinates):
    try:
        return client.directions(coordinates=coordinates, profile='driving-car', format='geojson')
    except Exception as e:
        st.error(f"Routing error: {e}")
        return None

def generate_map(assignments, destination):
    m = folium.Map(location=destination, zoom_start=12, tiles='CartoDB Positron')
    colors = ['red', 'blue', 'green', 'orange', 'purple']
    for i, (driver, riders) in enumerate(assignments.items()):
        if not riders: continue
        color = colors[i % len(colors)]
        coords = [st.session_state.driver_data[driver]['latlon']] + [p['latlon'] for p in riders] + [destination]
        ors_coords = [(lon, lat) for lat, lon in coords]
        route = get_route(ors_coords)
        if route:
            folium.GeoJson(route, name=driver, style_function=lambda x: {'color': color}).add_to(m)
        for p in riders:
            folium.Marker(p['latlon'], tooltip=p['name'], icon=folium.Icon(color=color)).add_to(m)
        folium.Marker(st.session_state.driver_data[driver]['latlon'], tooltip=f"{driver} (Driver)", icon=folium.Icon(color='black')).add_to(m)
    folium.Marker(destination, tooltip="Church", icon=folium.Icon(color='cadetblue')).add_to(m)
    return m

# -------------------- UI --------------------
st.sidebar.title("🚗 FLC Ride Input")
role = st.sidebar.selectbox("Are you a...", ["Driver", "Passenger"], key="role_select")
with st.sidebar.form(key="input_form_unique"):
    name = st.text_input("Your Name", key="name_input")
    address = st.text_input("Starting Address", key="addr_input")
    if role == "Driver":
        seats = st.number_input("Available Seats", 1, 10, step=1, key="seats_input")
        direction = st.selectbox("Driving to or from church?", ["To Church", "From Church"], key="dir_input")
    submitted = st.form_submit_button("Add to List")
    if submitted:
        latlon = geocode_address(address)
        if latlon:
            if role == "Driver":
                st.session_state.drivers.append({"name": name, "address": address, "latlon": latlon, "seats": seats, "direction": direction})
            else:
                st.session_state.passengers.append({"name": name, "address": address, "latlon": latlon})
            st.success("✅ Entry added!")
        else:
            st.warning("⚠️ Address not found.")

# -------------------- DESTINATION + OPTIMIZATION --------------------
st.title("🚘 FLC Philly Ride Coordinator")
st.markdown("Help us organize rides to church by assigning drivers to passengers.")
dest_address = st.text_input("📍 Church Destination Address", "600 Snyder Ave, Philadelphia, PA", key="dest_input")
dest_latlon = geocode_address(dest_address)
if st.button("✅ Optimize Rides", key="optimize_button"):
    if dest_latlon and st.session_state.drivers and st.session_state.passengers:
        st.session_state.driver_data = {d['name']: d for d in st.session_state.drivers}
        assignments, unassigned = assign_passengers_to_drivers_efficiently(st.session_state.drivers, st.session_state.passengers)
        st.session_state.assignments = assignments
        st.session_state.unassigned = unassigned
        st.session_state.destination = dest_latlon
        rows = [{"Driver": d, "Passenger": p['name'], "Passenger Address": p['address']} for d, plist in assignments.items() for p in plist]
        rows += [{"Driver": "Unassigned", "Passenger": p['name'], "Passenger Address": p['address']} for p in unassigned]
        st.session_state.assignments_df = pd.DataFrame(rows)
        st.session_state.map_render = generate_map(assignments, dest_latlon)
    else:
        st.error("🚫 Make sure drivers, passengers, and destination are filled in.")

# -------------------- RESULTS --------------------
if not st.session_state.assignments_df.empty:
    st.subheader("📋 Ride Assignments")
    st.dataframe(st.session_state.assignments_df, use_container_width=True)
    st.download_button("📥 Download CSV", data=st.session_state.assignments_df.to_csv(index=False), file_name="ride_assignments.csv")
    if st.session_state.unassigned:
        st.warning("⚠️ These passengers were not assigned:")
        for p in st.session_state.unassigned:
            st.write(f"- {p['name']} at {p['address']}")
    st.subheader("🗺️ Route Map")
    st_folium(st.session_state.map_render, width=1000, height=600)

# -------------------- SIDEBAR TABLES --------------------
st.sidebar.markdown("---")
st.sidebar.subheader("👥 Drivers")
st.sidebar.dataframe(pd.DataFrame(st.session_state.drivers))
st.sidebar.subheader("🚶 Passengers")
st.sidebar.dataframe(pd.DataFrame(st.session_state.passengers))

# -------------------- PRELOAD RIDES --------------------
PRELOADED_RIDE_DATA = {
    "Joel": [
        {"name": "Zaida", "address": "4039 Locust Street, Philadelphia, PA 19104", "phone": "443-857-8282"},
        {"name": "Jeffrey", "address": "Harnwell College House, Philadelphia, PA", "phone": "267-290-0504"},
        {"name": "Adelaide", "address": "3817 Spruce Street, Stouffer Mayer College House, Philadelphia, PA", "phone": "862-302-8469"},
    ],
    "Will": [
        {"name": "Evelyne", "address": "6301 Overbrook Ave, Philadelphia, PA 19151", "phone": "346-606-6994"}
    ],
    "Daniel A. or Darian": [
        {"name": "Nana", "address": "115 N 32nd Street, Philadelphia, PA 19104", "phone": "445-345-0380"},
        {"name": "Daniel E.", "address": "300 N Budd Street, Philadelphia, PA 19104", "phone": "203-962-3642"},
        {"name": "Alvin", "address": "3714 Haverford Ave, Philadelphia, PA 19104", "phone": "445-214-8237"},
    ],
    "Phoenix": [
        {"name": "Lily", "address": "216 Lakeview Drive, Ridley Park, PA 19078", "phone": "484-365-3592"},
    ],
    "Sa’ryah": [
        {"name": "Cameron", "address": "5913 Reach St, Philadelphia, PA 19120", "phone": "215-986-5223"},
        {"name": "Brandon J", "address": "6001 Tulip Street, Philadelphia, PA 19135", "phone": "267-241-9528"},
        {"name": "Henrita", "address": "9457 Lansford Street, Philadelphia, PA 19114", "phone": "215-669-4701"},
    ],
    "Jerome": [
        {"name": "Cornell", "address": "1544 N Redfield Street, Philadelphia, PA 19151", "phone": "215-375-2252"},
        {"name": "Leah", "address": "5224 Lebanon Ave, Philadelphia, PA 19131", "phone": "610-901-1130"},
    ],
    "Uber": [
        {"name": "Elizabeth", "address": "1500 Hamilton St, Philadelphia, PA", "phone": "610-417-8261"},
        {"name": "Liz’s Friend", "address": "1500 Hamilton St, Philadelphia, PA", "phone": None},
        {"name": "Fred", "address": "2212 N Camac St., Philadelphia, PA", "phone": "267-938-1829"},
        {"name": "Gaelle", "address": "1603 N Broad Street, Philadelphia, PA 19122", "phone": "857-258-1642"},
    ]
}

if st.checkbox("📥 Load pre-assigned drivers and passengers for 06/29/25?"):
    for driver, passengers in PRELOADED_RIDE_DATA.items():
        st.session_state.drivers.append({
            "name": driver,
            "address": "TBD",
            "latlon": geocode_address("600 Snyder Ave, Philadelphia, PA"),
            "seats": len(passengers),
            "direction": "To Church"
        })
        for p in passengers:
            latlon = geocode_address(p['address'])
            if latlon:
                st.session_state.passengers.append({"name": p['name'], "address": p['address'], "phone": p['phone'], "latlon": latlon})
    st.success("✅ Loaded predefined roster!")
