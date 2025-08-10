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
    if "provider" not in st.session_state:
        st.session_state.provider = "auto"

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
        
        # Tempo
        pace = st.text_input(
            "Tempo (min/km)",
            value=st.session_state.pace,
            key="pace",
            help="Format: MM:SS, t.ex. 5:30"
        )
        
        st.divider()
        
        # Avancerade inställningar
        with st.expander("Avancerade inställningar"):
            # Provider-val
            provider_options = ["auto"]
            if "ORS_API_KEY" in st.secrets:
                provider_options.append("ors")
            if "GRAPHHOPPER_API_KEY" in st.secrets:
                provider_options.append("graphhopper")
            if len(provider_options) > 2:
                provider_options.append("both")
            
            st.session_state.provider = st.selectbox(
                "Routing-provider",
                provider_options,
                format_func=lambda x: {
                    "auto": "Automatisk (välj bästa)",
                    "ors": "OpenRouteService",
                    "graphhopper": "GraphHopper (ofta mer exakt)",
                    "both": "Testa båda (jämför resultat)"
                }.get(x, x),
                help="GraphHopper ger ofta mer exakta rundor"
            )
            
            # Visa API-status
            st.caption("API-nycklar konfigurerade:")
            if "ORS_API_KEY" in st.secrets:
                st.caption("✓ OpenRouteService")
            else:
                st.caption("✗ OpenRouteService")
            if "GRAPHHOPPER_API_KEY" in st.secrets:
                st.caption("✓ GraphHopper")
            else:
                st.caption("✗ GraphHopper")
        
        st.divider()
        
        # Startpunkt
        st.subheader("Startpunkt")
        start_method = st.radio(
            "Välj metod",
            ["address", "map"],
            format_func=lambda x: "Adress" if x == "address" else "Klick på karta",
            key="start_method"
        )
        
        if start_method == "address":
            start_address = st.text_input(
                "Startadress",
                placeholder="T.ex. Kungsgatan 1, Stockholm",
                key="start_address"
            )
            if st.button("Geokoda start", key="geocode_start"):
                coords = geocode_address(start_address)
                if coords:
                    st.session_state.start_coords = coords
                    st.success(f"Startpunkt: {coords[0]:.4f}, {coords[1]:.4f}")
                else:
                    st.error("Kunde inte hitta adressen")
        
        # Slutpunkt för point-to-point
        if mode == "point-to-point":
            st.divider()
            st.subheader("Slutpunkt")
            end_method = st.radio(
                "Välj metod",
                ["address", "map"],
                format_func=lambda x: "Adress" if x == "address" else "Klick på karta",
                key="end_method"
            )
            
            if end_method == "address":
                end_address = st.text_input(
                    "Slutadress",
                    placeholder="T.ex. Stureplan, Stockholm",
                    key="end_address"
                )
                if st.button("Geokoda slut", key="geocode_end"):
                    coords = geocode_address(end_address)
                    if coords:
                        st.session_state.end_coords = coords
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
                        st.session_state.route_seed, st.session_state.provider
                    )
                    
                    route_info = get_best_route(
                        st.session_state.start_coords,
                        st.session_state.end_coords if mode == "point-to-point" else None,
                        distance,
                        tolerance,
                        mode,
                        st.session_state.route_seed,
                        st.session_state.provider,
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
            returned_objects=["last_object_clicked_coords"]
        )
        
        # Hantera kartklick
        if map_data and "last_object_clicked_coords" in map_data and map_data["last_object_clicked_coords"]:
            clicked = map_data["last_object_clicked_coords"]
            coords = (clicked["lat"], clicked["lng"])
            
            if st.session_state.map_click_mode == "start" or st.session_state.mode == "loop":
                st.session_state.start_coords = coords
                address = reverse_geocode(coords[0], coords[1])
                st.info(f"Startpunkt satt: {address or f'{coords[0]:.4f}, {coords[1]:.4f}'}")
            else:
                st.session_state.end_coords = coords
                address = reverse_geocode(coords[0], coords[1])
                st.info(f"Slutpunkt satt: {address or f'{coords[0]:.4f}, {coords[1]:.4f}'}")
    
    with col2:
        st.subheader("Sammanfattning")
        
        if st.session_state.route_info:
            route = st.session_state.route_info
            
            # Visa statistik
            st.metric("Distans", f"{route.distance/1000:.2f} km")
            st.metric("Höjdökning", f"{route.elevation_gain:.0f} m")
            st.metric("Uppskattad tid", str(route.estimated_time).split('.')[0])
            st.metric("Provider", route.provider)
            
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