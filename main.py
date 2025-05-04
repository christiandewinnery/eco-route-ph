# EcoRoute PH: Emissions Analyzer - Developed by Christian Dewin Nery
# Optimized for Sustainable Transport Planning in the Philippines

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import matplotlib.pyplot as plt
import folium
import geojson
import os
import openrouteservice

# ----------- Constants and Config -----------
ORS_API_KEY = "5b3ce3597851110001cf6248e66fc3a2783949d4adb55466f48fc2a9"
client = openrouteservice.Client(key=ORS_API_KEY)

# Emission factors in kg CO₂ per tonne-km
# These are estimated default values and can be replaced with country-specific or CORSIA/IPCC/ISO-based data.
# Sources to consider: DENR-EMB, Department of Energy (Philippines), ICAO CORSIA, IPCC Guidelines, ISO 14064
EMISSION_FACTORS = {
    'truck': {'diesel': 0.12, 'biodiesel': 0.08},
    'train': {'diesel': 0.03, 'electric': 0.01},
    'ship': {'heavy_fuel_oil': 0.015}
}

routes = []
route_counter = {}
distance_unit = "km"
mass_unit = "tonnes"

# ----------- Utility Functions -----------
def convert_distance(value):
    return value * 1.60934 if distance_unit == "mi" else value

def convert_mass(value):
    return value / 1000 if mass_unit == "kg" else value

def geocode_address(address):
    try:
        result = client.pelias_search(text="Philippines, " + address)
        coords = result['features'][0]['geometry']['coordinates']
        return coords[1], coords[0]
    except:
        return None

def get_route_and_distance(coords_from, coords_to):
    try:
        route = client.directions(
            coordinates=[(coords_from[1], coords_from[0]), (coords_to[1], coords_to[0])],
            profile='driving-car',
            format='geojson'
        )
        geometry = route['features'][0]['geometry']['coordinates']
        distance_km = route['features'][0]['properties']['segments'][0]['distance'] / 1000
        return distance_km, [(lat, lon) for lon, lat in geometry]
    except:
        return None, []

# ----------- GUI Functions -----------
def update_table():
    table.delete(*table.get_children())
    for r in routes:
        table.insert("", "end", values=(
            r['Route Name'], r['Transport'], r['Fuel'],
            r[f'Distance ({distance_unit})'], r[f'Mass ({mass_unit})'], r['CO2 Emissions (kg)']
        ))

def update_total_emissions():
    total = sum(r['CO2 Emissions (kg)'] for r in routes)
    total_label.config(text=f"Total emissions: {total:.2f} kg CO₂")

def add_route():
    transport = transport_var.get()
    fuel = fuel_var.get()
    name = route_name_entry.get().strip()
    from_address = from_entry.get().strip()
    to_address = to_entry.get().strip()

    try:
        mass = float(mass_entry.get())
        mass_t = convert_mass(mass)
    except ValueError:
        messagebox.showerror("Invalid Input", "Cargo mass must be a number.")
        return

    coords_from = geocode_address(from_address)
    coords_to = geocode_address(to_address)
    if not coords_from or not coords_to:
        messagebox.showerror("Geocoding Error", "Could not find one or both addresses.")
        return

    if manual_distance.get():
        try:
            distance = float(distance_entry.get())
            distance_km = convert_distance(distance)
            route_coords = [coords_from, coords_to]
        except ValueError:
            messagebox.showerror("Invalid Input", "Distance must be a number.")
            return
    else:
        distance_km, route_coords = get_route_and_distance(coords_from, coords_to)
        if distance_km is None:
            messagebox.showerror("Route Error", "Could not calculate route.")
            return
        if distance_unit == "mi":
            distance_km /= 1.60934
        distance_entry.delete(0, tk.END)
        distance_entry.insert(0, f"{distance_km:.2f}")

    try:
        factor = EMISSION_FACTORS[transport][fuel]
        emissions = distance_km * mass_t * factor
    except KeyError:
        messagebox.showerror("Invalid Selection", "Transport and fuel combination not supported.")
        return

    base_name = name if name else "Route"
    route_counter[base_name] = route_counter.get(base_name, 0) + 1
    full_name = f"{base_name}_{route_counter[base_name]}"

    routes.append({
        'Route Name': full_name,
        'Transport': transport,
        'Fuel': fuel,
        f'Distance ({distance_unit})': round(distance_km, 2),
        f'Mass ({mass_unit})': round(mass_t, 2),
        'CO2 Emissions (kg)': round(emissions, 2),
        'Coordinates': route_coords
    })

    update_table()
    update_total_emissions()
    clear_form()

def clear_form():
    route_name_entry.delete(0, tk.END)
    from_entry.delete(0, tk.END)
    to_entry.delete(0, tk.END)
    mass_entry.delete(0, tk.END)
    distance_entry.delete(0, tk.END)

def delete_selected():
    selected = table.selection()
    if not selected:
        return
    name = table.item(selected[0])['values'][0]
    global routes
    routes = [r for r in routes if r['Route Name'] != name]
    update_table()
    update_total_emissions()

def export_excel():
    if not routes:
        return
    filepath = filedialog.asksaveasfilename(defaultextension=".xlsx")
    if filepath:
        df = pd.DataFrame(routes)
        df['Generated By'] = 'Christian Dewin Nery'
        df.to_excel(filepath, index=False)

def export_geojson():
    if not routes:
        return
    features = []
    for r in routes:
        coords = r.get('Coordinates', [])
        if not coords:
            continue
        feature = geojson.Feature(
            geometry=geojson.LineString(coords),
            properties={
                "Exported By": "Christian Dewin Nery using EcoRoute PH",
                "Route": r['Route Name'],
                "Transport": r['Transport'],
                "Fuel": r['Fuel'],
                "CO2 Emissions (kg)": r['CO2 Emissions (kg)']
            }
        )
        features.append(feature)
    file_path = filedialog.asksaveasfilename(defaultextension=".geojson")
    if file_path:
        with open(file_path, "w", encoding="utf-8") as f:
            geojson.dump(geojson.FeatureCollection(features), f, indent=2)

def plot_emissions():
    if not routes:
        return
    names = [r['Route Name'] for r in routes]
    values = [r['CO2 Emissions (kg)'] for r in routes]
    plt.figure(figsize=(10, 5))
    plt.bar(names, values, color='green')
    plt.title("CO₂ Emissions per Route")
    plt.ylabel("CO₂ (kg)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

def show_map():
    if not routes:
        return
    m = folium.Map(location=[13.41, 122.56], zoom_start=6)
    for r in routes:
        coords = r.get('Coordinates', [])
        emission = r['CO2 Emissions (kg)']
        color = "green" if emission < 50 else "orange" if emission < 150 else "red"
        if coords:
            folium.PolyLine(coords, color=color, weight=5, opacity=0.7).add_to(m)
            folium.Marker(coords[0], tooltip=f"Start: {r['Route Name']}", icon=folium.Icon(color='blue')).add_to(m)
            folium.Marker(coords[-1], tooltip=f"End: {r['Route Name']}\n{emission:.2f} kg", icon=folium.Icon(color=color)).add_to(m)
    m.save("map.html")
    os.startfile("map.html")

def apply_unit_change():
    global distance_unit, mass_unit
    distance_unit = distance_var.get()
    mass_unit = mass_var.get()
    update_table()
    update_total_emissions()

# ----------- GUI Setup -----------
root = tk.Tk()

# Add About menu
menubar = tk.Menu(root)
help_menu = tk.Menu(menubar, tearoff=0)
help_menu.add_command(
    label="About EcoRoute PH",
    command=lambda: messagebox.showinfo(
        "About",
        "EcoRoute PH\nDeveloped by Christian Dewin Nery\n\nA route-based CO₂ emissions calculator for sustainable fuel logistics in the Philippines."
    )
)
menubar.add_cascade(label="Help", menu=help_menu)
root.config(menu=menubar)

root.title("EcoRoute PH by Christian Dewin Nery")
root.geometry("1000x800")

route_name_entry = tk.Entry(root)
from_entry = tk.Entry(root)
to_entry = tk.Entry(root)
mass_entry = tk.Entry(root)
distance_entry = tk.Entry(root)
manual_distance = tk.BooleanVar(value=False)
transport_var = tk.StringVar()
fuel_var = tk.StringVar()

# Widgets
for label_text, widget in [
    ("Route name (optional):", route_name_entry),
    ("From address:", from_entry),
    ("To address:", to_entry),
    ("Cargo mass:", mass_entry),
    ("Distance (if manual):", distance_entry)
]:
    tk.Label(root, text=label_text).pack()
    widget.pack()

tk.Checkbutton(root, text="Enter distance manually", variable=manual_distance).pack()

# Dropdowns
tk.Label(root, text="Transport type:").pack()
transport_dropdown = ttk.Combobox(root, textvariable=transport_var, values=list(EMISSION_FACTORS.keys()), state='readonly')
transport_dropdown.pack()

fuel_dropdown = ttk.Combobox(root, textvariable=fuel_var, state='readonly')
fuel_dropdown.pack()

def update_fuels(event=None):
    t = transport_var.get()
    if t in EMISSION_FACTORS:
        fuel_dropdown['values'] = list(EMISSION_FACTORS[t].keys())
        fuel_var.set(fuel_dropdown['values'][0])

transport_var.set(list(EMISSION_FACTORS.keys())[0])
update_fuels()
transport_dropdown.bind("<<ComboboxSelected>>", update_fuels)

tk.Button(root, text="Add Route", command=add_route).pack(pady=5)

columns = ("Route Name", "Transport", "Fuel", f"Distance ({distance_unit})", f"Mass ({mass_unit})", "CO2 Emissions (kg)")
table = ttk.Treeview(root, columns=columns, show="headings")
for col in columns:
    table.heading(col, text=col)
    table.column(col, width=130)
table.pack()

tk.Button(root, text="Delete Selected", command=delete_selected).pack(pady=5)
tk.Button(root, text="Export to Excel", command=export_excel).pack(pady=5)
tk.Button(root, text="Export to GeoJSON", command=export_geojson).pack(pady=5)
tk.Button(root, text="Show Emissions Graph", command=plot_emissions).pack(pady=5)
tk.Button(root, text="Show Map", command=show_map).pack(pady=5)

unit_frame = tk.Frame(root)
unit_frame.pack(pady=5)
tk.Label(unit_frame, text="Distance Unit:").pack(side="left")
distance_var = tk.StringVar(value="km")
ttk.Combobox(unit_frame, textvariable=distance_var, values=["km", "mi"], state='readonly', width=5).pack(side="left", padx=5)
tk.Label(unit_frame, text="Mass Unit:").pack(side="left")
mass_var = tk.StringVar(value="tonnes")
ttk.Combobox(unit_frame, textvariable=mass_var, values=["tonnes", "kg"], state='readonly', width=5).pack(side="left", padx=5)
tk.Button(unit_frame, text="Apply Units", command=apply_unit_change).pack(side="left", padx=10)

total_label = tk.Label(root, text="Total emissions: 0.00 kg CO₂", font=("Arial", 10, "bold"))
total_label.pack(pady=5)

root.mainloop()
