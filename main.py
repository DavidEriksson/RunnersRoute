"""
Huvudapplikation för Streamlit löparruttplanerare
"""

import streamlit as st
from streamlit_folium import st_folium
from datetime import datetime

# Importera moduler
from config import DEFAULT_DISTANCE, DEFAULT_TOLERANCE, DEFAULT_PACE, DEFAULT_CENTER
from geocoding import geocode_address, reverse_geocode
from routing import get_best_route, create_cache_key
from map_utils import create_map
from utils import create_gpx

def init_session_state():
    """Initiera session state"""
    if "start_coords" not in st.session_state:
        st.session_state.start_coords = None
    if "end_coords" not in st.session_state:
        st.session_state.end_coords = None
    if "distance" not in st.session_state:
        st.session_state.distance = DEFAULT_DISTANCE
    if "mode" not in st.session_state:
        st.session_state.mode = "loop"
    if "tolerance" not in st.session_state:
        st.session_state.tolerance = DEFAULT_TOLERANCE
    if "pace" not in st.session_state:
        st.session_state.pace = DEFAULT_PACE
    if "route_info" not in st.session_state:
        st.session_state.route_info = None
    if "map_click_mode" not in st.session_state:
        st.session_state.map_click_mode = "start"
    if "route_seed" not in st.session_state:
        st.session_state.route_seed = 0
    if "last_start_address" not in st.session_state:
        st.session_state.last_start_address = ""
    if "last_end_address" not in st.session_state:
        st.session_state.last_end_address = ""

def main():
    """Huvudfunktion för Streamlit-appen"""
    st.set_page_config(
        page_title="Löparruttplanerare",
        page_icon="🏃",
        layout="wide"
    )
    
    init_session_state()
    
    st.title("Löparruttplanerare")
    st.markdown("Planera din perfekta löprunda med exakt distans och GPX-export")
    
    # Sidebar för inställningar
    with st.sidebar:
        st.header("Inställningar")
        
        # Lägesval
        mode = st.radio(
            "Ruttläge",
            ["loop", "point-to-point"],
            format_func=lambda x: "Loop (start = mål)" if x == "loop" else "Point-to-point",
            key="mode"
        )
        
        # Distans
        distance = st.number_input(
            "Distans (km)",
            min_value=0.5,
            max_value=50.0,
            value=st.session_state.distance,
            step=0.5,
            key="distance"
        )
        
        # Tolerans
        tolerance = st.slider(
            "Tolerans (%)",
            min_value=1.0,
            max_value=20.0,
            value=st.session_state.tolerance,
            step=1.0,
            key="tolerance",
            help="Hur mycket rutten får avvika från önskad distans"
        )
        
        st.divider()
        
        # Startpunkt
        st.subheader("Startpunkt")
        start_address = st.text_input(
            "Startadress",
            placeholder="T.ex. Kungsgatan 1, Stockholm",
            key="start_address",
            help="Skriv en adress eller klicka på kartan"
        )
        
        # Auto-geokoda när adressen ändras
        if start_address and start_address != st.session_state.last_start_address:
            with st.spinner("Söker adress..."):
                coords = geocode_address(start_address)
                if coords:
                    st.session_state.start_coords = coords
                    st.session_state.last_start_address = start_address
                    st.success(f"Startpunkt: {coords[0]:.4f}, {coords[1]:.4f}")
                else:
                    st.error("Kunde inte hitta adressen")
        
        # Slutpunkt för point-to-point
        if mode == "point-to-point":
            st.divider()
            st.subheader("Slutpunkt")
            end_address = st.text_input(
                "Slutadress",
                placeholder="T.ex. Stureplan, Stockholm",
                key="end_address",
                help="Skriv en adress eller klicka på kartan"
            )
            
            # Auto-geokoda när adressen ändras
            if end_address and end_address != st.session_state.last_end_address:
                with st.spinner("Söker adress..."):
                    coords = geocode_address(end_address)
                    if coords:
                        st.session_state.end_coords = coords
                        st.session_state.last_end_address = end_address
                        st.success(f"Slutpunkt: {coords[0]:.4f}, {coords[1]:.4f}")
                    else:
                        st.error("Kunde inte hitta adressen")
        
        st.divider()
        
        # Generera rutt
        col_gen1, col_gen2 = st.columns(2)
        with col_gen1:
            generate_button = st.button("Generera rutt", type="primary", use_container_width=True)
        with col_gen2:
            regenerate_button = st.button("Ny variant", type="secondary", use_container_width=True, 
                                         disabled=not st.session_state.start_coords,
                                         help="Generera en annan rutt med samma inställningar")
        
        if generate_button or regenerate_button:
            if not st.session_state.start_coords:
                st.error("Välj en startpunkt först!")
            elif mode == "point-to-point" and not st.session_state.end_coords:
                st.error("Välj en slutpunkt först!")
            else:
                # Öka seed för ny variant
                if regenerate_button:
                    st.session_state.route_seed += 10  # Öka med 10 för att garantera olika resultat
                
                with st.spinner("Beräknar rutt..."):
                    # Skapa cache-nyckel med seed och provider
                    coords = [[st.session_state.start_coords[1], st.session_state.start_coords[0]]]
                    if mode == "point-to-point":
                        coords.append([st.session_state.end_coords[1], st.session_state.end_coords[0]])
                    
                    cache_key = create_cache_key(
                        coords, distance, mode, tolerance, 
                        st.session_state.route_seed, "auto"  # Alltid använd auto
                    )
                    
                    route_info = get_best_route(
                        st.session_state.start_coords,
                        st.session_state.end_coords if mode == "point-to-point" else None,
                        distance,
                        tolerance,
                        mode,
                        st.session_state.route_seed,
                        "auto",  # Alltid använd auto
                        cache_key
                    )
                    
                    if route_info:
                        st.session_state.route_info = route_info
                        st.success(f"Rutt genererad med {route_info.provider}!")
                    else:
                        st.error("Kunde inte generera rutt. Försök justera inställningarna.")
    
    # Huvudinnehåll
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Karta")
        
        # Info om klickläge
        if st.session_state.mode == "point-to-point":
            click_mode = st.radio(
                "Klickläge",
                ["start", "end"],
                format_func=lambda x: "Sätt startpunkt" if x == "start" else "Sätt slutpunkt",
                horizontal=True,
                key="map_click_mode"
            )
        
        # Skapa karta
        center = list(st.session_state.start_coords) if st.session_state.start_coords else DEFAULT_CENTER
        
        m = create_map(
            center,
            st.session_state.route_info,
            st.session_state.start_coords,
            st.session_state.end_coords if st.session_state.mode == "point-to-point" else None
        )
        
        # Visa karta med interaktion
        map_data = st_folium(
            m,
            key="map",
            width=None,
            height=500,
            returned_objects=["last_object_clicked"]
        )
        
        # Hantera kartklick
        if map_data and map_data.get("last_object_clicked"):
            clicked = map_data["last_object_clicked"]
            if clicked.get("lat") and clicked.get("lng"):
                coords = (clicked["lat"], clicked["lng"])
                
                if st.session_state.map_click_mode == "start" or st.session_state.mode == "loop":
                    st.session_state.start_coords = coords
                    address = reverse_geocode(coords[0], coords[1])
                    st.info(f"Startpunkt satt: {address or f'{coords[0]:.4f}, {coords[1]:.4f}'}")
                    st.rerun()
                else:
                    st.session_state.end_coords = coords
                    address = reverse_geocode(coords[0], coords[1])
                    st.info(f"Slutpunkt satt: {address or f'{coords[0]:.4f}, {coords[1]:.4f}'}")
                    st.rerun()
    
    with col2:
        st.subheader("Sammanfattning")
        
        if st.session_state.route_info:
            route = st.session_state.route_info
            
            # Visa statistik
            st.metric("Distans", f"{route.distance/1000:.2f} km")
            st.metric("Höjdökning", f"{route.elevation_gain:.0f} m")
            
            # Beräkna tid baserat på standardtempo
            pace_min = 5.5  # Standard 5:30 min/km
            time_minutes = (route.distance / 1000) * pace_min
            hours = int(time_minutes // 60)
            mins = int(time_minutes % 60)
            time_str = f"{hours}:{mins:02d}" if hours > 0 else f"{mins} min"
            st.metric("Uppskattad tid", time_str)
            
            # Toleransinfo
            target_distance = st.session_state.distance * 1000
            deviation = ((route.distance - target_distance) / target_distance) * 100
            if abs(deviation) <= st.session_state.tolerance:
                st.success(f"Inom tolerans: {deviation:+.1f}%")
            else:
                st.warning(f"Utanför tolerans: {deviation:+.1f}%")
                st.info("Tips: Klicka 'Ny variant' för att testa andra rutter")
            
            st.divider()
            
            # GPX-export
            st.subheader("Export")
            
            gpx_name = st.text_input(
                "Ruttnamn",
                value=f"Löprunda {datetime.now().strftime('%Y-%m-%d')}",
                key="gpx_name"
            )
            
            if st.button("Ladda ner GPX", use_container_width=True):
                gpx_content = create_gpx(route, gpx_name)
                st.download_button(
                    label="Spara GPX-fil",
                    data=gpx_content,
                    file_name=f"{gpx_name.replace(' ', '_')}.gpx",
                    mime="application/gpx+xml",
                    use_container_width=True
                )
        else:
            st.info("Generera en rutt för att se sammanfattning")
    
    # Footer
    st.divider()
    st.markdown(
        """
        <div style='text-align: center; color: gray; font-size: 0.8em;'>
        Skapad för löpare | 
        Använder OpenRouteService, GraphHopper & OpenStreetMap
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()