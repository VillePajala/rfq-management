# Tarjouspyyntöagentti — MVP-vaatimukset

**Lähde:** CGI-stakeholder (2026-04-21)
**Tila:** Raakamateriaali, pohja jatkoa varten (MVP + täysi versio).
**Säilytysohje:** Tämä tiedosto on kopio alkuperäisestä stakeholder-viestistä. Älä muokkaa
sisältöä — uudet tarkennukset ja iteraatiot kirjataan erillisiin speksaus-dokumentteihin
(`docs/mvp_spec.md`, `docs/full_spec.md`, …). Tämän tarkoitus on toimia referenssinä
siihen, mitä stakeholder alun perin toivoi.

---

Tarjouspyyntöagentti MVP-vaatimukset

-    Valvoo ja hakee tarjouspyynnöt, tietopyynnöt ja markkinavuoropuhelut tarjouspalvelu.fi:stä ja Hilmasta.
o    Hilmasta rajapinnan kautta
o    tarjouspalvelu.fi:stä robotin avulla (ei ilmaista rajapintaa tarjolla)
-    Rajaa haettavan materiaalin CPV-koodilla.
-    Kun uusi hankintamenettely on julkaistu, hakee materiaalin yhteen sovittuun SharePoint-työtilaan (josta sitten alkuun käsin siirretään varsinaiseen oppo-työtilaan kunhan sellainen on perustettu).
o    Tulevaisuudessa työtilan perustaminen yms. voidaan mahdollisesti automatisoida (riippuen oikeuksista yms.).
-    Tekee tarjouspyynnöstä alustavan analyysin:
o    Hankinnan kohde, onko kyseessä ostolaskujärjestelmä, tekoälykonsultointia vai mitä. Tunnistetaan ensisijaisesti asiasanapohjaisesti.
o    Tekee alustavan reitityksen talon sisällä (ei kuitenkaan spämmää vielä), tähän tarvitaan esim. excel jossa reitityssäännöt (ruokahuolto=>Aromi, kiinteistöhallinta=>Koki, infrapalvelut=>GTO).
o    Hankinnan aikarajat, milloin kysymysten jättö, milloin tarjouksen jättö.
o    Onko jotain muuta mitä voidaan helposti tunnistaa materiaalista, esim.
    Hankinnan arvioitu kokoluokka
    Rajattu vs. avoin menettely
    Pisteytysmekanismi (laatu vs. hinta)
    Onko sopimusta mukana ja onko varaumat kielletty
-    Agentti lähettää alustavan analyysin sekä linkin haettuun materiaaliin sovittuun sähköpostilaatikkoon. Ei siis reititetä suoraan MVP-versiolla.
o    Tulevaisuudessa reitittää automaattisesti talon sisällä vastuutiimeille, mutta ei kuormiteta nyt "spämmillä" ennen kuin ratkaisua on ajettu ja testattu.
-    Nice to have -toimintoja MVP:hen (voitaisiin toteuttaa mikäli työmäärä marginaalinen)
o    Luo kalenterimerkinnän tarjouksen kriittisille päivämäärille (iCal).
o    Luodaan pilvipohjainen kalenterinäkymä, josta voi seurata kaikkien CGI:n aktiivisten kilpailutusten osalta tilannetta. Ts. sieltä näkisi mitkä on nyt jo delegoitu, mitkä odottavat vielä kotipesää. Sieltä siis näkisi helposti kokonaistilanteen. Olisiko mahdollista myös täydentää näkymää siten että esim. kun kysymykset on jätetty, niin siellä olisi tilatieto päivitettynä (toki kysymyksiähän voi jättää aina myös lisää)? Tänne pitäisi luoda myös yksinkertainen kirjautuminen ja tätä portaalia voisi tulevaisuudessa kehittää esim. hintatietojen keräämiseen ja simulointiin.
-    Avoimet kysymykset
o    Onko riskiä, että liitetiedostojen mukana tulee haittaohjelmia, miten voitaisiin tehdä virustarkistus (vai luotetaanko siihen että tarjousportaalissa on jo tarkistettu)?
o    Miten muodostetaan reititystiedosto ja varmistetaan että se on kattava?
o    Pilviympäristö pitäisi selvittää, saadaanko joku Publicin Azure tenant-käyttöön? Tälle pitää myös DPSC:t yms. hoitaa (datahan on lähtökohtaisesti julkista).

Yleisenä ajatuksena on, että ensimmäinen versio olisi kevyt ja sitä käytettäisiin koekäytössä rinnalla esim. kuukauden päivät. Sen myötä saataisiin sitten kokemusta ja ymmärrystä, miten ratkaisun tulisi toimia ja millaisia erikoistapauksia tulisi huomioida. Kun saadaan nämä vaatimukset tarkennettua, uskoisin että ensimmäisen MVP-version saisimme kasaan hyvinkin nopeasti. Mutta tehdään niin että kun nuo vaatimukset on nyt tarkennettu MVP:lle, Ville voisi tehdä työmääräarvion niistä
