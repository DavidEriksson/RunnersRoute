🏃 Streamlit Löparruttplanerare
En komplett webbapplikation för löpare som vill planera perfekta löprundor med exakt distans, höjddata och GPX-export.

✨ Funktioner
🗺️ Interaktiv kartvy - Välj start/slutpunkt genom adress eller klick på kartan
🔄 Två ruttlägen:
Loop - Start och mål på samma plats (använder ORS round_trip)
Point-to-point - Olika start och slutpunkt med automatisk via-punktsoptimering
📏 Exakt distans - Ange önskad distans och få en rutt inom din tolerans (±5% som standard)
📊 Detaljerad statistik:
Total distans
Höjdökning
Uppskattad tid baserat på ditt tempo
💾 GPX-export - Ladda ner rutten för din GPS-klocka eller mobil
⚡ Smart caching - Snabbare laddning av tidigare sökningar
📱 Responsiv design - Fungerar på mobil, surfplatta och desktop
🚀 Installation
Förutsättningar
Python 3.8 eller högre
En OpenRouteService API-nyckel (gratis)
Steg-för-steg
Klona eller ladda ner projektet
bash
git clone https://github.com/ditt-namn/running-route-app.git
cd running-route-app
Installera dependencies
bash
pip install -r requirements.txt
