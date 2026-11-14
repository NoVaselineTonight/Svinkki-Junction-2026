/* Svinkki add-on: the Finnish dictionary (see i18n.js). Every interface string of app.js and extras.js, and the
   texts the server writes on the home page and the demo path, in Finnish for a Finnish bank's customers.
   English text is the key. Lines are "English => Suomi"; strings built from pieces (names, amounts, dates) are
   anchored patterns further down. Terms used throughout: Etusivu, Omat asiasi, Asetukset, Keskustelut, Sinulle,
   Kuukausikatsaus, Päivän visa, Kannattaa katsoa, Käyttövara, Säästösuunnitelma, Mitä voin kysyä?. */
(function () {
  'use strict';
  if (!window.SvI18n || !window.SvI18n.add) return;

  var LINES = [
  // ---------- the static page (index.html) ----------
  'Svinkki - your money coach => Svinkki – rahavalmentajasi',
  'Back to Home => Takaisin etusivulle',
  'New conversation => Uusi keskustelu',
  'New => Uusi',
  'Settings => Asetukset',
  'Loading... => Ladataan...',
  'Svinkki needs JavaScript to run. => Svinkki tarvitsee toimiakseen JavaScriptin.',
  'Junction 2026 prototype with synthetic data. S-Pankki brand used with permission. => Junction 2026 -prototyyppi, jossa on synteettistä dataa. S-Pankin brändiä käytetään luvalla.',

  // ---------- errors and waiting ----------
  "I can't get through right now. Check your connection and try again. => Yhteys ei toimi juuri nyt. Tarkista nettiyhteytesi ja yritä uudelleen.",
  'Give me a moment to catch up, then try again. => Anna minulle hetki, niin pysyn mukana. Yritä sitten uudelleen.',
  'Something went wrong on my side. Please try again in a moment. => Minun päässäni meni jokin pieleen. Yritä hetken päästä uudelleen.',
  'Something went wrong on my side. Please try again. => Minun päässäni meni jokin pieleen. Yritä uudelleen.',
  "That's switched off in your choices. You can turn it on in Settings. => Tämä on pois päältä valinnoissasi. Voit kytkeä sen päälle Asetuksissa.",
  'The daily quiz is off. You can turn it on in Settings. => Päivän visa on pois päältä. Voit kytkeä sen päälle Asetuksissa.',
  "That's no longer available. => Tämä ei ole enää saatavilla.",
  "That's a bit long for me. Could you shorten it? => Tuo on minulle hieman liian pitkä. Voisitko lyhentää sitä?",
  "I didn't quite get that. Could you put it another way? => En aivan ymmärtänyt. Voisitko sanoa sen toisin?",
  'Please log in again. => Kirjaudu sisään uudelleen.',
  'Turn on "Analyse my transactions" in Settings to use this. => Ota Asetuksista käyttöön ”Analysoi tapahtumani”, niin voit käyttää tätä.',
  'That took me too long, sorry. Please try again in a moment. => Tähän meni liian kauan, anteeksi. Yritä hetken päästä uudelleen.',
  'Try again => Yritä uudelleen',
  "I couldn't load part of this page. Check your connection. => En saanut ladattua osaa tästä sivusta. Tarkista nettiyhteytesi.",
  'Reading your question... => Luen kysymystäsi...',
  'Checking your numbers... => Tarkistan lukujasi...',
  'Looking through your transactions... => Käyn läpi tapahtumiasi...',
  'Putting the answer together... => Kokoan vastausta...',
  'Still working. A long question takes a while... => Työ on vielä kesken. Pitkä kysymys vie hetken...',
  'Almost there... => Melkein valmis...',
  'Waiting for the answer => Odotetaan vastausta',
  'Checking... => Tarkistetaan...',
  'Saving... => Tallennetaan...',
  'Loading categories... => Ladataan luokkia...',
  'Loading transactions... => Ladataan tapahtumia...',
  'Picking a customer... => Valitaan asiakasta...',
  'Loading demo customers... => Ladataan demoasiakkaita...',
  'Calculating... => Lasketaan...',
  'Searching... => Haetaan...',
  'Moving... => Siirretään...',
  'Cancelling... => Perutaan...',
  'Asking Claude... => Kysytään Claudelta...',
  'Looking… => Katsotaan…',
  'Reading your text… => Luetaan tekstiäsi…',
  'Opening the conversation... => Avataan keskustelua...',
  'Preparing your check-in... => Valmistellaan katsaustasi...',
  "Picking today's questions for you... => Valitaan sinulle tämän päivän kysymykset...",
  'Picking new questions for you... => Valitaan sinulle uusia kysymyksiä...',

  // ---------- common words ----------
  'Cancel => Peruuta', 'Save => Tallenna', 'Delete => Poista', 'Close => Sulje', 'Send => Lähetä', 'Start => Aloita',
  'Yes => Kyllä', 'No => Ei', 'On => Päällä', 'Off => Pois', 'None => Ei yhtään', 'One => Yksi', 'Up to three => Enintään kolme',
  'More => Lisää', 'Why => Miksi', 'Done. => Valmis.', 'Saved. => Tallennettu.', 'Noted. => Selvä.', 'Nothing => Ei mitään',
  'Transactions => Tapahtumat', 'Transaction => Tapahtuma', 'Category => Luokka', 'Name => Nimi', 'Amount => Summa',
  'All => Kaikki', 'Table => Taulukko', 'Results => Tulokset', 'Item => Tuote', 'Bill => Lasku', 'Receipt => Kuitti',
  'Answer => Vastaus', 'Conversation => Keskustelu', 'Customer => Asiakas', 'Other => Muu', 'link => linkki',
  'Group => Ryhmä', 'You => Sinä', 'Typical => Tyypillinen', 'Average => Keskiarvo', 'Finland => Suomi', 'Yours => Sinun',
  'Open Settings => Avaa Asetukset', 'Kept => Tallennettu', 'Undo => Kumoa', 'Forget => Unohda', 'Remembered => Muistettu',
  '(needed) => (pakollinen)', 'Switched off => Pois päältä', 'Not now => Ei nyt', 'Accept => Hyväksy',
  'Suggestion => Ehdotus', 'Show me => Näytä minulle', 'Try another => Kokeile toista', 'Check => Tarkista',
  "One sentence with a figure I couldn't verify was removed from the AI's answer. => Poistin tekoälyn vastauksesta yhden lauseen, jonka lukua en voinut tarkistaa.",
  "The AI's wording contained a figure I couldn't verify, so I replaced it with a checked answer. => Tekoälyn vastauksessa oli luku, jota en voinut tarkistaa, joten korvasin sen tarkistetulla vastauksella.",
  'AI is offline, so this is a simpler answer. => Tekoäly ei ole nyt käytössä, joten tämä on yksinkertaisempi vastaus.',
  'Tap a column to see its value. => Napauta saraketta nähdäksesi sen arvon.',
  'Built-in answer => Sisäänrakennettu vastaus',
  'In S-mobiili => S-mobiilissa',
  'This week => Tällä viikolla',
  'unknown error => tuntematon virhe',
  'Explain => Selitä', 'Cancelled => Peruttu', 'Moved => Siirretty', 'Move money => Siirrä rahaa', 'Move more => Siirrä lisää',
  'Latest transactions => Viimeisimmät tapahtumat', 'Earlier savings and investments => Aiemmat säästöt ja sijoitukset',
  'Savings => Säästöt', 'Saved => Säästetty', 'Spent => Käytetty', 'spent => käytetty', 'Money in => Tulot',
  'left over => jäi yli', 'more out than in => enemmän ulos kuin sisään', 'in total => yhteensä', 'a month => kuukaudessa',
  'this week => tällä viikolla', 'Spending => Kulutus', 'Fuel => Polttoaine', 'Groceries => Ruokakauppa',
  'Month => Kuukausi', 'Basket => Kori', 'Filters => Suodattimet', 'Topics => Aiheet', 'Date => Päivä', 'What => Mitä',
  'Count => Määrä', 'Where => Missä', 'Regular => Säännölliset', 'Unexpected => Odottamattomat', 'Everyday => Arki',
  'Now => Nyt', 'Then => Sitten', 'A day => Päivässä', 'A month => Kuukaudessa', 'In total => Yhteensä', 'Goal => Tavoite',

  // ---------- categories, baskets, targets ----------
  'Regular essentials => Perusmenot', 'Unexpected necessities => Odottamattomat menot', 'Everyday spending => Arkikulutus',
  'Bills and things you need every month => Laskut ja asiat, joita tarvitset joka kuukausi',
  'Costs you could not plan for => Kulut, joihin et voinut varautua',
  'Choices you make day to day => Valinnat, joita teet päivittäin',
  'Regular essentials: bills and things you need every month => Perusmenot: laskut ja asiat, joita tarvitset joka kuukausi',
  'Unexpected necessities: costs you could not plan for => Odottamattomat menot: kulut, joihin et voinut varautua',
  'Everyday spending: choices you make day to day => Arkikulutus: valinnat, joita teet päivittäin',
  'Spending split between the three baskets => Kulutus jaettuna kolmeen koriin',
  'Three baskets => Kolme koria',
  'Housing => Asuminen', 'Utilities => Käyttökulut', 'Restaurant => Ravintolat', 'Restaurants => Ravintolat',
  'Fast food => Pikaruoka', 'Bar => Baarit', 'Bars => Baarit', 'Taxi => Taksit', 'Taxis => Taksit',
  'Public transport => Joukkoliikenne', 'Parking => Pysäköinti', 'Pharmacy => Apteekki', 'Doctor => Lääkäri',
  'Dentist => Hammaslääkäri', 'Other health => Muu terveys', 'Home improvement => Kodin kunnostus',
  'Electronics => Elektroniikka', 'Furniture => Huonekalut', 'Clothing => Vaatteet', 'Hobbies => Harrastukset',
  'Books => Kirjat', 'Shopping => Ostokset', 'Events => Tapahtumat', 'Cinema => Elokuvat', 'Gym & sports => Kuntoilu ja urheilu',
  'Entertainment => Viihde', 'Flights => Lennot', 'Hotels => Hotellit', 'Travel agency => Matkatoimisto',
  'Car rental => Autovuokraus', 'Travel => Matkailu', 'Savings & investments => Säästöt ja sijoitukset', 'Salary => Palkka',
  'Other income => Muut tulot', 'Transfer out => Siirto pois', 'Night out => Ilta ulkona', 'Nights out => Illat ulkona',
  'Dining out => Ulkona syöminen', 'Income => Tulot', 'night_out => Ilta ulkona', 'regular => Perusmenot',
  'unexpected => Odottamattomat menot', 'everyday => Arkikulutus', 'Grocery => Ruokakauppa', 'Rent => Vuokra',
  'Fuel purchases => Polttoaineostokset',
  'Mon => Ma', 'Tue => Ti', 'Wed => Ke', 'Thu => To', 'Fri => Pe', 'Sat => La', 'Sun => Su',
  'Jan => Tammi', 'Feb => Helmi', 'Mar => Maalis', 'Apr => Huhti', 'May => Touko', 'Jun => Kesä', 'Jul => Heinä',
  'Aug => Elo', 'Sep => Syys', 'Oct => Loka', 'Nov => Marras', 'Dec => Joulu',
  'January => tammikuu', 'February => helmikuu', 'March => maaliskuu', 'April => huhtikuu', 'June => kesäkuu',
  'July => heinäkuu', 'August => elokuu', 'September => syyskuu', 'October => lokakuu', 'November => marraskuu',
  'December => joulukuu',

  // ---------- login ----------
  'Demo only => Vain demo',
  'Who are you today? => Kuka olet tänään?',
  'A prototype with synthetic data. In the bank app you would already be signed in. => Prototyyppi, jossa on synteettistä dataa. Pankin sovelluksessa olisit jo kirjautunut sisään.',
  'Try as a random customer => Kokeile satunnaisena asiakkaana',
  'Picks a random synthetic customer who uses the bank as their main account. => Valitsee satunnaisen synteettisen asiakkaan, jonka pääpankki tämä on.',
  'Random customers are not available right now. Please pick one of the examples below. => Satunnaisia asiakkaita ei ole nyt saatavilla. Valitse jokin alla olevista esimerkeistä.',
  'Or pick an example => Tai valitse esimerkki',
  'No demo customers are available. => Demoasiakkaita ei ole saatavilla.',
  'Goes out and eats out regularly: taxis, bars and nights out to ask about. => Käy säännöllisesti ulkona ja ravintoloissa: taksit, baarit ja illanvietot antavat paljon kysyttävää.',
  'Sets money aside every month and wants to know how fast the goals can be reached. => Säästää rahaa joka kuukausi ja haluaa tietää, kuinka nopeasti tavoitteet saavutetaan.',
  'Family-age high earner with a large, steady income and bigger bills. => Perheikäinen suurituloinen, jolla on suuret ja vakaat tulot sekä isommat laskut.',
  'Often runs close to or below zero before payday; safe-to-spend matters here. => Tili on usein nollan tuntumassa tai alle ennen palkkapäivää; käyttövara on tässä tärkeä.',
  'Thinking about buying a first home; applied for a mortgage. => Haaveilee ensimmäisestä kodista ja on hakenut asuntolainaa.',
  'Retired or close to it, with steady, careful spending. => Eläkkeellä tai lähellä sitä, kulutus on tasaista ja harkittua.',

  // ---------- consent, welcome, settings controls ----------
  'Analyse my transactions => Analysoi tapahtumani',
  'I need this to answer anything. I only look at your own transactions. => Tarvitsen tämän voidakseni vastata mihinkään. Katson vain sinun omia tapahtumiasi.',
  'Let an AI help with the wording => Anna tekoälyn auttaa sanamuodoissa',
  'It sees the figures behind your answer, never your name or account number. => Se näkee vastauksen taustalla olevat luvut, mutta ei koskaan nimeäsi tai tilinumeroasi.',
  "The AI isn't connected right now, so you get my built-in answers either way. => Tekoäly ei ole nyt yhdistettynä, joten saat joka tapauksessa omat sisäänrakennetut vastaukseni.",
  'Compare me with people like me => Vertaa minua samankaltaisiin ihmisiin',
  'Compare your spending with groups of 20+ similar customers. Only group totals are used. => Vertaa kulutustasi vähintään 20 samankaltaisen asiakkaan ryhmiin. Käytössä ovat vain ryhmien yhteissummat.',
  'Give me suggestions => Anna minulle ehdotuksia',
  'I may suggest things, like putting leftover money aside. Nothing happens unless you say yes. => Saatan ehdottaa esimerkiksi ylijäämärahan laittamista säästöön. Mitään ei tapahdu, ellet sano kyllä.',
  'Turn on "Analyse my transactions" to continue. => Ota käyttöön ”Analysoi tapahtumani”, niin voit jatkaa.',
  'Your choices => Valintasi',
  "I'm Svinkki, your money coach. I read your own transactions to answer your questions. => Olen Svinkki, rahavalmentajasi. Luen omia tapahtumiasi vastatakseni kysymyksiisi.",
  'An AI helps with the wording; it never sees your name or account. => Tekoäly auttaa sanamuodoissa, mutta se ei koskaan näe nimeäsi tai tiliäsi.',
  "The AI isn't connected right now, so I'll answer with my built-in know-how. The figures are just as exact. => Tekoäly ei ole nyt yhdistettynä, joten vastaan omalla osaamisellani. Luvut ovat yhtä tarkkoja.",
  'Money only moves when you approve it, and only to your own S-Bank savings or funds. You can change these choices any time in Settings. => Rahaa siirretään vain, kun hyväksyt sen, ja vain omaan S-Pankin säästöösi tai rahastoihisi. Voit muuttaa näitä valintoja milloin tahansa Asetuksissa.',
  'Hi! => Hei!',
  'Off => Pois',
  'Weekly => Viikoittain', 'Every 2 weeks => Kahden viikon välein', 'Monthly => Kuukausittain',
  'Check-in => Katsaus',
  'A short summary of your money with a few ideas. => Lyhyt yhteenveto rahoistasi ja muutama ajatus.',
  'Ideas in a check-in => Ehdotuksia katsauksessa',
  'None, at most one idea, or up to three. => Ei yhtään, enintään yksi tai enintään kolme ehdotusta.',
  'Weekly challenge => Viikkohaaste',
  'One small optional challenge from your own habits. => Yksi pieni vapaaehtoinen haaste omista tavoistasi.',
  'Daily quiz => Päivän visa',
  'Guess what you spent. It helps you notice habits. => Arvaa, paljonko käytit. Se auttaa huomaamaan omat tavat.',
  'How often I check in => Kuinka usein teen katsauksen',
  'What I may do => Mitä saan tehdä',
  'Show what the AI saw => Näytä, mitä tekoäly näki',
  'Nothing has been sent to an AI model in this session. => Tekoälymallille ei ole lähetetty mitään tämän istunnon aikana.',
  'Data sent to the AI model => Tekoälymallille lähetetyt tiedot',
  'What the AI saw => Mitä tekoäly näki',
  'Exactly what was last sent to the AI model, with no names or account details. => Täsmälleen se, mitä tekoälymallille lähetettiin viimeksi, ilman nimiä tai tilitietoja.',
  'AI model (demo setup) => Tekoälymalli (demon asetus)',
  'Erase my data => Poista tietoni',
  'This deletes your choices, Your things, your conversations and everything else I have stored about you. It cannot be undone. Your bank transactions are not touched. => Tämä poistaa valintasi, Omat asiasi, keskustelusi ja kaiken muun, mitä olen tallentanut sinusta. Sitä ei voi perua. Pankkitapahtumiasi ei kosketa.',
  'Yes, erase everything => Kyllä, poista kaikki',
  'Your data => Tietosi',
  'Your transactions stay in the bank. I only read your own. => Tapahtumasi pysyvät pankissa. Luen vain omiasi.',
  'Your choices and Your things are saved so I can use them next time. => Valintasi ja Omat asiasi tallennetaan, jotta voin käyttää niitä ensi kerralla.',
  'Your conversations are saved so you can return to them. "Erase my data" removes them too. => Keskustelusi tallennetaan, jotta voit palata niihin. ”Poista tietoni” poistaa nekin.',
  'Reset demo => Nollaa demo',
  'This takes the demo back to the very beginning for every demo customer and logs you out. The AI key and model are kept. => Tämä vie demon aivan alkuun jokaisen demoasiakkaan osalta ja kirjaa sinut ulos. Tekoälyn avain ja malli säilyvät.',
  'Yes, start over => Kyllä, aloita alusta',
  'Log out => Kirjaudu ulos',
  'Hackathon prototype for the S-Pankki challenge. Synthetic data. => Hackathon-prototyyppi S-Pankin haasteeseen. Synteettistä dataa.',
  'For the person running the demo. Customers never see this in the bank app. => Demon pitäjälle. Asiakkaat eivät koskaan näe tätä pankin sovelluksessa.',
  'That does not look like a Claude API key. It starts with "sk-ant-". => Tämä ei näytä Clauden API-avaimelta. Sen alku on ”sk-ant-”.',
  'The AI setup can only be changed on the computer that runs Svinkki. => Tekoälyn asetuksia voi muuttaa vain tietokoneella, jolla Svinkki toimii.',
  'Claude is set up to answer the chat. => Claude vastaa keskusteluun.',
  'A Gemini key is in use. Save a Claude key to switch to Claude. => Käytössä on Gemini-avain. Tallenna Claude-avain vaihtaaksesi Claudeen.',
  'No AI model is connected. Answers come from the built-in rules. => Tekoälymallia ei ole yhdistetty. Vastaukset tulevat sisäänrakennetuista säännöistä.',
  'No Claude key is saved. => Claude-avainta ei ole tallennettu.',
  'A Claude key is saved. => Claude-avain on tallennettu.',
  'It comes from the environment, so a key saved here is not used until that one is removed. => Se tulee ympäristöstä, joten tähän tallennettua avainta ei käytetä ennen kuin se poistetaan.',
  'Open Svinkki at http://localhost on the computer that runs it to change the key or the model. => Avaa Svinkki osoitteessa http://localhost tietokoneella, jolla se toimii, vaihtaaksesi avaimen tai mallin.',
  'Leave empty to keep the saved key => Jätä tyhjäksi säilyttääksesi tallennetun avaimen',
  'Test the key => Testaa avain',
  'Saved. Use "Test the key" to check that it works. => Tallennettu. Tarkista toimivuus ”Testaa avain” -painikkeella.',
  'Claude answered. The key works. => Claude vastasi. Avain toimii.',
  'Model => Malli', 'Replace the key => Vaihda avain', 'Claude API key => Clauden API-avain',
  'Opus gives the best answers. Haiku is the cheapest and the fastest. => Opus antaa parhaat vastaukset. Haiku on halvin ja nopein.',
  'Saved in a file on this computer. It is never shown again and never sent to the browser. => Tallennettu tämän tietokoneen tiedostoon. Sitä ei näytetä enää koskaan eikä lähetetä selaimelle.',

  // ---------- home ----------
  'Ask me anything about your money, even the hard questions. => Kysy minulta mitä tahansa rahoistasi, myös vaikeita asioita.',
  'Ask about your money => Kysy rahoistasi',
  'Ask Svinkki a question => Kysy Svinkiltä',
  'Goals, receipts, contracts and more => Tavoitteet, kuitit, sopimukset ja paljon muuta',
  'Example questions => Esimerkkikysymyksiä',
  'Ready for you => Valmiina sinulle',
  'For you => Sinulle',
  'Your things => Omat asiasi',
  'Conversations => Keskustelut',
  'Your check-in => Kuukausikatsaus',
  'Worth a look => Kannattaa katsoa',
  'Nothing unusual this month. => Tässä kuussa ei ole mitään epätavallista.',
  'Something to look at => Katsottavaa',
  'Delete conversation => Poista keskustelu',
  'What can I spend this week? => Paljonko voin käyttää tällä viikolla?',
  'What kind of spender am I? => Millainen kuluttaja olen?',
  'Can I afford it? => Onko minulla varaa siihen?',
  'How can I save more? => Miten voin säästää enemmän?',
  'Where did my money go? => Mihin rahani menivät?',
  'Where is my money leaking? => Missä rahani vuotavat?',
  'Give me a challenge => Anna minulle haaste',
  'Will I make it to payday? => Riittävätkö rahani palkkapäivään?',
  'Can I afford a 50 euro dinner? => Onko minulla varaa 50 euron illalliseen?',
  'What is safe for me to spend this week? => Paljonko voin turvallisesti käyttää tällä viikolla?',
  'How should I split my next salary? => Miten jakaisin seuraavan palkkani?',
  'How much could I save if I reduced dining out by 20%? => Paljonko säästäisin, jos vähentäisin ulkona syömistä 20 %?',
  'What do I buy most? => Mitä ostan eniten?',
  'How much do I spend on energy drinks? => Paljonko käytän energiajuomiin?',
  'Show my receipts => Näytä kuittini',
  'When was my balance below zero? => Milloin saldoni oli alle nollan?',
  'Your account => Tilisi',
  'Your accounts => Tilisi',
  'Current account => Käyttötili',
  'Savings and investments => Säästöt ja sijoitukset',
  'S-Bank current account => S-Pankin käyttötili',
  'Safe to spend => Käyttövara',
  'Short until payday => Rahat eivät riitä palkkapäivään',
  'Next payday => Seuraava palkkapäivä',
  'On track => Kunnossa', 'Tight => Tiukoilla', 'Over budget => Yli budjetin',
  'Today => Tänään', 'Yesterday => Eilen', 'not saved => ei tallennettu',

  // ---------- conversation ----------
  'Conversation with Svinkki => Keskustelu Svinkin kanssa',
  'Your question => Kysymyksesi',
  'What can I ask? => Mitä voin kysyä?',
  'Everything I can do => Kaikki, mitä osaan',
  'These are examples. Ask in your own words, in English or Finnish. => Nämä ovat esimerkkejä. Kysy omin sanoin, suomeksi tai englanniksi.',
  'Things to ask => Kysyttävää',
  'See everything I can do => Katso kaikki, mitä osaan',
  'Read this receipt => Lue tämä kuitti',
  'Start a new conversation => Aloita uusi keskustelu',
  'This conversation is no longer here. => Tätä keskustelua ei enää ole.',
  'No check-in is ready yet, or check-ins are off. You can choose how often in Settings. => Katsausta ei ole vielä valmiina, tai katsaukset ovat pois päältä. Voit valita tiheyden Asetuksissa.',
  'Daily quiz => Päivän visa',
  'My check-in => Kuukausikatsaukseni',
  'What if I spent less? => Entä jos käyttäisin vähemmän?',
  'Compare with others => Vertaa muihin',
  'My challenge => Haasteeni',
  'Keeping answers is not available yet. => Vastausten tallentaminen ei ole vielä käytössä.',
  'A receipt => Kuitti',

  // ---------- What can I ask ----------
  'My spending => Kulutukseni',
  'Where it went, in your three baskets => Mihin rahat menivät, kolmessa korissa',
  'Before you buy, and until payday => Ennen ostosta ja palkkapäivään asti',
  'Save and plan => Säästä ja suunnittele',
  'Saving, a home loan, investing => Säästäminen, asuntolaina, sijoittaminen',
  'Set something up => Ota käyttöön',
  'A goal, a challenge, a note, the quiz => Tavoite, haaste, muistiinpano, visa',
  'Compared with others => Vertailu muihin',
  'Only when you ask => Vain kun pyydät',
  'Leaks and habits => Vuodot ja tavat',
  'Small costs that add up => Pienet kulut, jotka kasautuvat',
  'My receipts => Kuittini',
  'Single products, and loan or fund texts => Yksittäiset tuotteet sekä laina- ja rahastotekstit',
  'How much did I spend on taxis last month? => Paljonko käytin takseihin viime kuussa?',
  'Show my three baskets for last month => Näytä kolme koriani viime kuulta',
  'What was my latest purchase? => Mikä oli viimeisin ostokseni?',
  'Browse my transactions => Selaa tapahtumiani',
  'Can I afford a 300 euro jacket? => Onko minulla varaa 300 euron takkiin?',
  'Check a purchase of my own => Tarkista oma ostokseni',
  'What kind of mortgage can I get approved for? => Minkä kokoisen asuntolainan voisin saada?',
  'What should I invest in? => Mihin minun kannattaisi sijoittaa?',
  'Try cutting a category with sliders => Kokeile karsia luokkaa liukusäätimillä',
  'I am saving 4000 euros for Japan by June 2027 => Säästän 4000 euroa Japaniin kesäkuuhun 2027 mennessä',
  'Remember that my rent goes up in January => Muista, että vuokrani nousee tammikuussa',
  "Today's quiz => Päivän visa",
  'Is my taxi spending normal? => Onko taksikulutukseni tavallista?',
  'How do I compare with people my age? => Vertaa minua muihin ikäisiini',
  'What is my area like? => Millainen on asuinalueeni?',
  'Compare a category with others => Vertaa luokkaa muihin',
  'Anything unusual this month? => Onko tässä kuussa jotain epätavallista?',
  'Any spending patterns? => Onko kulutuksessani kuvioita?',
  'Read a receipt I paste => Lue liittämäni kuitti',
  'Explain a loan or fund text => Selitä laina- tai rahastoteksti',
  'Help => Apua', 'What can I ask => Mitä voin kysyä',

  // ---------- transactions ----------
  'Wrong category? Tap the purchase to fix it. => Väärä luokka? Napauta ostosta korjataksesi sen.',
  'No transactions match. => Yksikään tapahtuma ei täsmää.',
  'No transactions matched. => Yksikään tapahtuma ei täsmännyt.',
  'Categories are not available right now. => Luokat eivät ole nyt saatavilla.',
  'Part of a night out => Osa iltaa ulkona',
  'Every purchase from this merchant => Kaikki ostokset tältä kauppiaalta',
  'See the transactions => Katso tapahtumat',
  'The period in transactions => Jakso tapahtumina',
  'Where this comes from => Mistä tämä tulee',
  'Browse transactions => Selaa tapahtumia',
  'Search, for example taxi => Hae, esimerkiksi taksi',
  'Search transactions => Hae tapahtumia',
  'All categories => Kaikki luokat',
  'Nights out only => Vain illat ulkona',
  'The transactions behind the quiz => Visan taustalla olevat tapahtumat',
  'The transactions behind this => Tämän taustalla olevat tapahtumat',
  'Showing the first rows only. => Näytetään vain ensimmäiset rivit.',

  // ---------- quiz ----------
  'Guess your spending this week. => Arvaa kulutuksesi tällä viikolla.',
  'Your guess in euros => Arviosi euroina',
  'Your guess => Arviosi',
  'Lock in my guess => Lukitse arvaukseni',
  'You spent => Käytit',
  'Spot on. => Täsmälleen oikein.',
  'No other question is available right now. => Toista kysymystä ei ole nyt saatavilla.',
  'Score saved to Your things => Pisteet tallennettu kohtaan Omat asiasi',
  'Saved to Your things => Tallennettu kohtaan Omat asiasi',
  'Quiz score => Visapisteet',
  'Picked for you by the AI coach => Tekoälyvalmentajan sinulle valitsema',
  'Picked for you => Valittu sinulle',
  'The answer => Vastaus',
  'Source: => Lähde:',
  'See my score => Näytä pisteeni',
  'Next question => Seuraava kysymys',
  'Your score => Pisteesi',
  'A perfect round. => Täydellinen kierros.',
  'A good round. New questions come tomorrow, or try another set now. => Hyvä kierros. Uudet kysymykset tulevat huomenna, tai kokeile uutta sarjaa jo nyt.',
  'Every answer teaches something. Try another set? => Jokainen vastaus opettaa jotain. Kokeile uutta sarjaa?',
  'New questions => Uudet kysymykset',
  'No questions are ready right now. => Kysymyksiä ei ole nyt valmiina.',
  'Answer a quiz question and your score shows up here. => Vastaa visakysymykseen, niin pisteesi näkyvät tässä.',
  'guessing accuracy => arvaustarkkuus',
  'How close your recent guesses were => Kuinka lähellä viimeisimmät arvauksesi olivat',
  'Questions answered => Vastattuja kysymyksiä',
  'Your guessing => Arvauksesi',
  'Spot on! => Täsmälleen oikein!',
  'Play today\'s quiz => Pelaa päivän visa',

  // ---------- check-in and suggestions ----------
  'Okay, we\'ll leave it for now. => Selvä, jätetään tämä toistaiseksi.',
  'Noted. I saved your choice. => Selvä. Tallensin valintasi.',
  "Okay, I won't suggest this again. No money was moved. => Selvä, en ehdota tätä enää. Rahaa ei siirretty.",
  "Okay, I'll remind you later. No money was moved. => Selvä, muistutan myöhemmin. Rahaa ei siirretty.",
  'This suggestion is no longer available. => Tämä ehdotus ei ole enää saatavilla.',
  'Here is the move. Nothing happens until you approve it. => Tässä siirto. Mitään ei tapahdu ennen kuin hyväksyt sen.',
  'Review the days your balance went below zero? => Käydäänkö läpi päivät, jolloin saldosi oli alle nollan?',
  'Start a small buffer? => Aloitetaanko pieni puskuri?',
  'Would you like to look at what drove it? => Haluatko katsoa, mikä sen aiheutti?',
  'Build buffer => Rakenna puskuri',

  // ---------- money moves ----------
  'Inside S-mobiili => S-mobiilin sisällä',
  'Approve this move? => Hyväksytäänkö tämä siirto?',
  'This move was cancelled. => Tämä siirto peruttiin.',
  'This offer has expired. Ask again and I will make a new one. => Tarjous on vanhentunut. Pyydä uudestaan, niin teen uuden.',
  'This move was already made. => Tämä siirto on jo tehty.',
  'Okay, nothing was moved. => Selvä, mitään ei siirretty.',
  'Nothing was moved. => Mitään ei siirretty.',
  'Move not made => Siirtoa ei tehty',
  'From => Mistä', 'To => Mihin', 'Balance after => Saldo siirron jälkeen',
  'Your current account => Käyttötilisi',
  'Your S-Bank current account => S-Pankin käyttötilisi',
  'S-Bank savings account => S-Pankin säästötili',
  'S-Bank global index fund => S-Pankin maailmanindeksirahasto',
  'S-Bank short-term interest fund => S-Pankin lyhyen koron rahasto',
  'Your own savings account in S-mobiili. You can move the money back at any time. => Oma säästötilisi S-mobiilissa. Voit siirtää rahat takaisin milloin tahansa.',
  'A fund that follows shares across the world. Suits money you can leave for five years or more. => Rahasto, joka seuraa osakkeita ympäri maailmaa. Sopii rahalle, jonka voit jättää viideksi vuodeksi tai pidemmäksi aikaa.',
  'Fund value goes up and down; you can get back less than you put in. => Rahaston arvo vaihtelee, ja voit saada takaisin vähemmän kuin sijoitit.',
  'A low-risk fund for money you may need within a year or two. => Matalan riskin rahasto rahalle, jota voit tarvita vuoden tai kahden sisällä.',
  'Low risk, but the value can still dip a little. => Matala riski, mutta arvo voi silti laskea hieman.',
  'Nothing moves until you approve. The money stays in S-mobiili. => Mitään ei siirretä ennen kuin hyväksyt. Rahat pysyvät S-mobiilissa.',
  'Nothing moves until you approve. => Mitään ei siirretä ennen kuin hyväksyt.',
  'Show the move => Näytä siirto',
  'Enter an amount above zero. => Syötä summa, joka on suurempi kuin nolla.',
  'That move is not possible. => Tämä siirto ei ole mahdollinen.',
  'Where to => Minne',
  'Amount in euros => Summa euroina',
  'Nothing moved yet. => Mitään ei ole vielä siirretty.',
  'A demo account built from synthetic data. Money only moves inside S-mobiili, after you approve it. => Demotili, joka on tehty synteettisestä datasta. Rahaa siirretään vain S-mobiilin sisällä, kun olet hyväksynyt sen.',
  'Demo: fund values do not change here. Money only moves after you approve it, and it stays in S-mobiili. => Demo: rahastojen arvot eivät muutu täällä. Rahaa siirretään vasta hyväksyntäsi jälkeen, ja se pysyy S-mobiilissa.',
  "I can only move money to your S-Bank savings account or an S-Bank fund in S-mobiili. => Voin siirtää rahaa vain S-Pankin säästötilillesi tai S-Pankin rahastoon S-mobiilissa.",
  'Tell me how much to move, in euros. => Kerro, paljonko siirretään, euroina.',
  'That is more than can be moved in one go here. => Tämä on enemmän kuin tässä voi siirtää kerralla.',
  'Nothing can be moved safely before payday: your balance is needed for bills and a small buffer. => Mitään ei voi siirtää turvallisesti ennen palkkapäivää: saldosi tarvitaan laskuihin ja pieneen puskuriin.',
  "I couldn't match that approval, so nothing was moved. Ask me again and I'll make a new offer. => En voinut yhdistää hyväksyntää mihinkään tarjoukseen, joten mitään ei siirretty. Pyydä uudestaan, niin teen uuden tarjouksen.",
  "That doesn't match the offer I made, so nothing was moved. Ask me again and I'll make a new one. => Tämä ei vastaa tekemääni tarjousta, joten mitään ei siirretty. Pyydä uudestaan, niin teen uuden.",
  'This offer has expired or was already used. Ask again and I will make a new one. => Tarjous on vanhentunut tai se on jo käytetty. Pyydä uudestaan, niin teen uuden.',
  "I'll show you the move and ask you to approve it first; the money stays in S-mobiili. => Näytän siirron ja pyydän sinua hyväksymään sen ensin; rahat pysyvät S-mobiilissa.",
  'It stays in S-mobiili, and you can see it under Your things. => Rahat pysyvät S-mobiilissa, ja näet ne kohdassa Omat asiasi.',
  'You asked me to remember this => Pyysit minua muistamaan tämän',
  'Saved to Your things: => Tallennettu kohtaan Omat asiasi:',

  // ---------- afford ----------
  'Not right now => Ei juuri nyt', 'Think twice => Harkitse kahdesti',
  'Left a day after it => Päivässä jää sen jälkeen',
  'Until payday => Palkkapäivään',
  'Safe to spend before it => Käyttövara ennen ostosta',
  'Left until payday => Jäljellä palkkapäivään',
  'What is it? => Mikä se on?', 'A jacket => Takki', 'Price in euros => Hinta euroina',
  'Enter a price above zero. => Syötä hinta, joka on suurempi kuin nolla.',
  'this => tämä',

  // ---------- challenges ----------
  'Your challenge => Haasteesi', 'Stop challenge => Lopeta haaste', 'Challenge => Haaste', 'Why these => Miksi nämä',
  'Pick one if you like. Skipping is fine. => Valitse yksi, jos haluat. Väliin jättäminen on ihan ok.',
  'Turn on weekly challenges => Ota viikkohaasteet käyttöön',
  'Challenges are off. One small optional challenge a week, built from your own habits. => Haasteet ovat pois päältä. Yksi pieni vapaaehtoinen haaste viikossa omien tapojesi pohjalta.',
  'No challenge right now. New ones come each week. => Ei haastetta juuri nyt. Uusia tulee joka viikko.',
  'Weekly challenge => Viikkohaaste',

  // ---------- explain a text, receipts ----------
  'Explain a text => Selitä teksti',
  'Paste text from a loan agreement or a fund prospectus => Liitä tähän tekstiä lainasopimuksesta tai rahaston esitteestä',
  'Text to explain => Selitettävä teksti',
  'Identity codes, account numbers, e-mail addresses and phone numbers are removed before anything is sent to an AI model. => Henkilötunnukset, tilinumerot, sähköpostiosoitteet ja puhelinnumerot poistetaan, ennen kuin mitään lähetetään tekoälymallille.',
  'Explain another text => Selitä toinen teksti',
  'Explaining a text is not available right now. => Tekstin selittäminen ei ole nyt käytettävissä.',
  'In plain words => Selkeästi sanottuna', 'Key points => Pääkohdat', 'Watch out for => Varo näitä',
  'Explained with the AI. => Selitetty tekoälyn avulla.', 'Explained without the AI. => Selitetty ilman tekoälyä.',
  'Read a receipt => Lue kuitti',
  'Read this receipt => Lue tämä kuitti',
  'Paste the text of a receipt => Liitä kuitin teksti',
  'For example from the receipts in S-mobiili. One product and its price per line. => Esimerkiksi S-mobiilin kuiteista. Yksi tuote ja sen hinta riviä kohti.',
  'Demo receipts => Demokuitit',
  'The receipt lines are simulated for this demo. => Kuittien rivit on simuloitu tätä demoa varten.',
  'Your receipts => Kuittisi',
  'No receipts in this period. => Tällä jaksolla ei ole kuitteja.',
  'What you buy => Mitä ostat', 'Most often => Useimmin', 'Biggest group => Suurin ryhmä', 'Treats => Herkut',
  'By product group => Tuoteryhmittäin', 'Also bought often => Ostat usein myös', 'Litres => Litrat',
  'A litre on average => Litra keskimäärin', 'From your receipts => Kuiteistasi', 'Bought => Ostettu',
  'A year at this pace => Vuodessa tällä tahdilla', 'Each time => Joka kerta', 'On these receipts => Näillä kuiteilla',
  'Your receipt => Kuittisi',
  'Each time, on average => Joka kerta keskimäärin',

  // ---------- cards ----------
  'Your month => Kuukautesi', 'By basket => Koreittain', 'Biggest areas => Suurimmat alueet',
  'safe to spend before payday => käyttövara ennen palkkapäivää', 'Short by about => Vajaa noin',
  'How it is worked out => Näin se lasketaan', 'Money in your account => Rahaa tililläsi',
  'Bills before payday => Laskut ennen palkkapäivää', 'Buffer for surprises => Puskuri yllätyksille',
  'Planned savings => Suunnitellut säästöt',
  'If you spent more => Jos käyttäisit enemmän', 'extra a year => ylimääräistä vuodessa',
  'Spending a month => Kulutus kuukaudessa', 'If you spent less => Jos käyttäisit vähemmän', 'saved a year => säästöä vuodessa',
  'Your spender type => Kuluttajatyyppisi', 'Ways to save more => Tapoja säästää enemmän',
  'Mortgage readiness => Asuntolainavalmius', 'Not a decision => Ei lainapäätös', 'possible loan => mahdollinen laina',
  'Home price with 15% down => Asunnon hinta 15 %:n omarahoituksella', 'Your own money needed => Tarvittava oma raha',
  'You and people like you => Sinä ja sinun kaltaisesi', 'No comparison is available yet. => Vertailua ei ole vielä saatavilla.',
  'What is typical? => Mikä on tavallista?',
  'About the same as most people like you => Suunnilleen sama kuin useimmilla sinun kaltaisillasi',
  'More than most people like you => Enemmän kuin useimmilla sinun kaltaisillasi',
  'Less than most people like you => Vähemmän kuin useimmilla sinun kaltaisillasi',
  'Compared with people like you => Vertailu sinun kaltaisiisi ihmisiin',
  ', approximate => , likimääräinen',
  'Investing basics => Sijoittamisen perusteet', 'Education only => Vain opetuskäyttöön',
  'of costs in your account. 3–6 months is a common aim. => kuluista tililläsi. 3–6 kuukautta on yleinen tavoite.',
  'Next step => Seuraava askel', 'Build the buffer first => Rakenna ensin puskuri',
  'Savings goal => Säästötavoite', 'Not reachable yet => Ei vielä saavutettavissa', 'to go => jäljellä',
  'Saving a month => Säästö kuukaudessa', 'Around => Noin',
  'Small leaks => Pienet vuodot', 'Forgotten subscriptions => Unohtuneet tilaukset', 'None found => Ei löytynyt',
  'Small buys => Pienostokset', 'Mostly => Enimmäkseen', 'By weekday => Viikonpäivittäin',
  'By hour of the day => Tunneittain', 'Everyday spending by weekday => Arkikulutus viikonpäivittäin',
  'Everyday spending by hour of the day => Arkikulutus kellonajoittain',
  'Repeating charges => Toistuvat veloitukset', 'Repeating charge => Toistuva veloitus',
  'Savings and investments => Säästöt ja sijoitukset', 'Worth a look => Kannattaa katsoa',
  'Your savings => Säästösi', 'No pattern found => Kuviota ei löytynyt',
  'withdrawal from savings => nosto säästöistä', 'withdrawals from savings => nostoa säästöistä',
  'No withdrawals from savings found. => Säästöistä ei löytynyt nostoja.', 'Investment withdrawals => Sijoitusnostot',
  'Until payday => Palkkapäivään', 'Payday => Palkkapäivä', 'Goes below zero => Menee alle nollan', 'Bills on the way => Tulevat laskut',
  'Your payday plan => Palkkapäiväsuunnitelmasi', 'Suggested split of your next salary => Ehdotettu jako seuraavalle palkallesi',
  'This is a plan. Nothing is transferred. => Tämä on suunnitelma. Mitään ei siirretä.',
  'Your area => Asuinalueesi', 'Typical income here => Alueen tyypillinen tulotaso', 'Rented homes => Vuokra-asunnot',
  'Latest purchase => Viimeisin ostos', 'Spending patterns => Kulutuskuviot', 'A pattern => Kuvio',
  'Goal plan => Tavoitesuunnitelma', 'Save as my goal => Tallenna tavoitteeksi',
  'You save now => Säästät nyt', 'Still to find => Vielä puuttuu', 'Ways to close the gap => Tapoja kuroa vaje umpeen',
  "Undone. I've forgotten that. => Kumottu. Olen unohtanut sen.",
  'Your year in money => Vuotesi rahana', 'The months ahead => Tulevat kuukaudet',
  'One category over time => Yksi luokka ajan yli', 'Your month explained => Kuukautesi selitettynä',
  'Your lowest points => Alimmat pisteesi', 'Your income => Tulosi', 'What your receipts show => Mitä kuittisi kertovat',
  'Your grocery trips => Ruokaostoksesi', 'Where groceries could give => Mistä ruokaostoksissa voisi joustaa',
  'Worth knowing => Hyvä tietää', 'Your investing plan => Sijoitussuunnitelmasi', 'What the sources say => Mitä lähteet kertovat',
  'Answer => Vastaus',
  'What if I spent less? => Entä jos käyttäisin vähemmän?',
  'Pick up to three areas, then slide. => Valitse enintään kolme aluetta ja säädä sitten liukusäätimillä.',
  'Areas to cut => Karsittavat alueet',
  'Up to three areas. Tap one to remove it first. => Enintään kolme aluetta. Poista ensin yksi napauttamalla sitä.',
  'What this is based on => Mihin tämä perustuu',
  'This compares you with groups of at least 20 similar customers. It needs "Compare me with people like me" in Settings. => Tämä vertaa sinua vähintään 20 samankaltaisen asiakkaan ryhmiin. Se vaatii Asetuksista valinnan ”Vertaa minua samankaltaisiin ihmisiin”.',
  'Names => Nimet',
  'Statistics Finland => Tilastokeskus',
  'Everything => Kaikki',

  // ---------- Your things ----------
  'Monthly saving target => Kuukausittainen säästötavoite', 'What I have learned => Mitä olen oppinut', 'Note => Muistiinpano',
  'Kept answer => Tallennettu vastaus',
  'Remove from Your things => Poista kohdasta Omat asiasi', 'Forget this => Unohda tämä',
  'This answer cannot be shown any more. => Tätä vastausta ei voi enää näyttää.',
  'You have no savings goal right now. Tell me about one in a conversation, for example "I am saving for Japan in 2027". => Sinulla ei ole säästötavoitetta juuri nyt. Kerro minulle sellaisesta keskustelussa, esimerkiksi ”Säästän Japaniin vuonna 2027”.',
  'saved so far => säästetty tähän mennessä', 'By => Mennessä', 'Needs about => Tarvitsee noin',
  'Target (€) => Tavoite (€)', 'Saved so far (€) => Säästetty tähän mennessä (€)', 'Save changes => Tallenna muutokset',
  'Remove goal => Poista tavoite', 'Give your goal a name. => Anna tavoitteellesi nimi.',
  'Enter a target above zero. => Syötä tavoite, joka on suurempi kuin nolla.',
  'Saved so far must be zero or more. => Säästetyn määrän on oltava nolla tai enemmän.',
  'Used to say what a purchase does to your goal. Nothing moves automatically. => Käytetään kertomaan, mitä ostos tekee tavoitteellesi. Mitään ei siirry automaattisesti.',
  'set aside each month => säästöön joka kuukausi', 'Euros a month => Euroa kuukaudessa', 'Remove target => Poista tavoite',
  'Enter zero or more. => Syötä nolla tai enemmän.',
  'Taken off first when I work out what is safe to spend. Nothing moves automatically. => Vähennetään ensimmäisenä, kun lasken käyttövaraa. Mitään ei siirry automaattisesti.',
  'Every purchase from one merchant => Kaikki ostokset yhdeltä kauppiaalta', 'One purchase => Yksi osto',
  'Nothing learned yet. Tell me when a purchase is in the wrong category, for example "that kebab was lunch". => En ole vielä oppinut mitään. Kerro minulle, kun ostos on väärässä luokassa, esimerkiksi ”se kebab oli lounas”.',
  'I offered to move => Tarjosin siirtoa',

  // ---------- extras.js (what is behind each figure) ----------
  "Worked out by the app's calculator. => Sovelluksen laskimella laskettu.",
  'A rough estimate from general knowledge, not from your account. => Likimääräinen arvio yleistiedosta, ei tilitiedoistasi.',
  'Taken from the checked summary of your account. => Otettu tilisi tarkistetusta yhteenvedosta.',
  'Taken from an earlier answer in this conversation. => Otettu tämän keskustelun aiemmasta vastauksesta.',
  'The number you gave me. => Luku, jonka annoit minulle.',
  'Added up by the app from your transactions. => Sovellus on laskenut yhteen tapahtumistasi.',
  'Filled in by the app from your data. => Sovellus on täyttänyt tämän tiedoistasi.',
  'The AI wrote the sentence; this number is a guess, so treat it as a rough range. => Tekoäly kirjoitti lauseen; tämä luku on arvaus, joten pidä sitä summittaisena.',
  'The AI wrote the sentence, not the number. => Tekoäly kirjoitti lauseen, ei lukua.',
  'What I was given for this answer => Mitä sain tätä vastausta varten',
  'I only keep this for my latest answer. You can see it under that one. => Säilytän tämän vain viimeisimmästä vastauksestani. Näet sen sen alta.',
  'Nothing to show for this answer. => Tästä vastauksesta ei ole mitään näytettävää.',
  'Not given: your name, your account number, shop names. => Ei annettu: nimeäsi, tilinumeroasi eikä kauppojen nimiä.',
  'I could not load that just now. => En saanut tätä ladattua juuri nyt.',
  '1 figure, filled in by code from your data. Tap it to see where it comes from. => 1 luku, jonka koodi on täyttänyt tiedoistasi. Napauta sitä nähdäksesi, mistä se tulee.'
  ];

  // ---------- helpers ----------
  var NB = '\u00a0';
  var MON_NOM = ['tammikuu', 'helmikuu', 'maaliskuu', 'huhtikuu', 'toukokuu', 'kesäkuu', 'heinäkuu', 'elokuu', 'syyskuu', 'lokakuu', 'marraskuu', 'joulukuu'];
  var MON_INE = ['tammikuussa', 'helmikuussa', 'maaliskuussa', 'huhtikuussa', 'toukokuussa', 'kesäkuussa', 'heinäkuussa', 'elokuussa', 'syyskuussa', 'lokakuussa', 'marraskuussa', 'joulukuussa'];
  var MON_ILL = ['tammikuuhun', 'helmikuuhun', 'maaliskuuhun', 'huhtikuuhun', 'toukokuuhun', 'kesäkuuhun', 'heinäkuuhun', 'elokuuhun', 'syyskuuhun', 'lokakuuhun', 'marraskuuhun', 'joulukuuhun'];
  var EN_MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  var EN_MON3 = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  function tr(s) { return window.SvI18n.t(s); }

  // "€1,583.50" -> "1 583,50 €"; a Finnish amount stays as it is.
  function fiMoney(x) {
    x = String(x);
    var m = /^([+-]?)€(\d[\d,]*)(\.\d+)?$/.exec(x);
    if (!m) return x;
    var whole = m[2].replace(/,/g, '').replace(/\B(?=(\d{3})+(?!\d))/g, NB);
    return m[1] + whole + (m[3] ? ',' + m[3].slice(1) : '') + ' €';
  }
  function monthIndex(word) {
    var w = String(word || '').toLowerCase();
    var i = MON_NOM.indexOf(w);
    if (i >= 0) return i;
    for (var k = 0; k < 12; k++) if (EN_MONTHS[k].toLowerCase() === w) return k;
    return -1;
  }
  // "elokuu" / "elokuu 2025" / "August" -> "elokuussa" ...; a range of dates -> "ajalla 1.8.–15.9."
  function inMonth(x) {
    var m = /^([A-Za-zäöÄÖ]+)( \d{4})?$/.exec(String(x));
    if (m) { var i = monthIndex(m[1]); if (i >= 0) return MON_INE[i] + (m[2] || ''); }
    var low = String(x).toLowerCase();
    if (low === 'last month') return 'viime kuussa';
    if (low === 'last week') return 'viime viikolla';
    if (low === 'the last two weeks') return 'viimeisen kahden viikon aikana';
    if (/\d/.test(x)) return 'ajalla ' + x;
    return x;
  }
  // "June 2027" -> "kesäkuuhun 2027 mennessä", a date "30.6.2027" -> "30.6.2027 mennessä"
  function byWhen(x) {
    var m = /^([A-Za-zäöÄÖ]+)( \d{4})?$/.exec(String(x));
    if (m) { var i = monthIndex(m[1]); if (i >= 0) return MON_ILL[i] + (m[2] || '') + ' mennessä'; }
    return x + ' mennessä';
  }
  function genEur(x) { return String(x).replace(/ €$/, ' euron'); }
  // "15 Oct" / "15 Oct 2027" -> "15.10." / "15.10.2027"
  function enDate(x) {
    var m = /^(\d{1,2}) ([A-Z][a-z]{2})(?: (\d{4}))?$/.exec(String(x));
    if (!m) return x;
    var i = EN_MON3.indexOf(m[2]);
    if (i < 0) return x;
    return m[1] + '.' + (i + 1) + '.' + (m[3] || '');
  }
  function when(x) {
    x = String(x);
    var m = /^(today|yesterday) at (\d\d:\d\d)$/.exec(x);
    if (m) return (m[1] === 'today' ? 'tänään' : 'eilen') + ' klo ' + m[2];
    return enDate(x);
  }
  function cat(x) {
    var s = String(x || '');
    var a = tr(s);
    if (a === s) a = tr(s.charAt(0).toUpperCase() + s.slice(1));
    return a.toLowerCase();
  }
  function dec(x) { return String(x).replace('.', ','); }

  var DEST_NOM = {
    'S-Bank savings account': 'S-Pankin säästötili', 'S-Bank global index fund': 'S-Pankin maailmanindeksirahasto',
    'S-Bank short-term interest fund': 'S-Pankin lyhyen koron rahasto', 'savings': 'säästösi', 'buffer': 'puskurisi',
    'Your S-Bank current account': 'S-Pankin käyttötilisi', 'Your current account': 'käyttötilisi'
  };
  // "to your X": where the money goes
  var DEST_TO = {
    'S-Bank savings account': 'S-Pankin säästötilillesi', 'S-Bank global index fund': 'S-Pankin maailmanindeksirahastoon',
    'S-Bank short-term interest fund': 'S-Pankin lyhyen koron rahastoon', 'savings': 'säästöihisi', 'buffer': 'puskuriisi'
  };
  function destTo(x) { return DEST_TO[x] || DEST_NOM[x] || tr(String(x)); }
  function destNom(x) { return DEST_NOM[x] || tr(String(x)); }

  var TRANS = { t: tr, inm: inMonth, inmc: function (x) { var r = inMonth(x); return r.charAt(0).toUpperCase() + r.slice(1); }, by: byWhen, gen: genEur, cat: cat, dest: destTo, destn: destNom, dec: dec, date: enDate, when: when,
                lc: function (x) { return String(x).toLowerCase(); } };

  var MCAP = '((?:[+-]?\\d[\\d\\s]*(?:,\\d+)?\\s€)|(?:[+-]?€\\d[\\d,]*(?:\\.\\d+)?))';
  var CAP = { M: MCAP, N: '(\\d+(?:[.,]\\d+)?)', T: '((?:(?!\\.\\s)[\\s\\S])+?)', Q: '(\\d+)', W: '([^.]+?)' };

  // Pattern from templates: {M} an amount, {N} a number, {Q} a whole number, {T} any text. The Finnish text refers
  // to the captures as {1}, {2}.. and may name a change: {1:inm} {1:by} {1:gen} {1:cat} {1:dest} {1:t} ...
  function P(en, fi) {
    var kinds = [];
    var src = en.replace(/[.*+?^$()[\]\\|]/g, '\\$&').replace(/\{([MNTQW])\}/g, function (m, k) { kinds.push(k); return CAP[k]; });
    var re = new RegExp('^' + src + '$');
    return [re, function () {
      var caps = Array.prototype.slice.call(arguments, 1, 1 + kinds.length);
      return fi.replace(/\{(\d)(?::(\w+))?\}/g, function (m, i, tn) {
        var v = caps[i - 1], k = kinds[i - 1];
        if (k === 'M') v = fiMoney(v);
        else if (k === 'N') v = dec(v);
        return tn && TRANS[tn] ? TRANS[tn](v) : v;
      });
    }];
  }

  // Finnish counted nouns: "5 tapahtumaa", "1 tapahtuma".
  var PL = {
    transaction: ['tapahtuma', 'tapahtumaa'], purchase: ['osto', 'ostoa'], payment: ['maksu', 'maksua'],
    month: ['kuukausi', 'kuukautta'], day: ['päivä', 'päivää'], time: ['kerta', 'kertaa'], line: ['rivi', 'riviä'],
    thing: ['asia', 'asiaa'], answer: ['vastaus', 'vastausta'], correction: ['korjaus', 'korjausta'],
    'repeating charge': ['toistuva veloitus', 'toistuvaa veloitusta'], customer: ['asiakas', 'asiakasta'],
    person: ['henkilö', 'henkilöä'], people: ['henkilöä', 'henkilöä'], question: ['kysymys', 'kysymystä'],
    figure: ['luku', 'lukua'], guess: ['arvaus', 'arvausta'], word: ['sana', 'sanaa'], found: ['löytyi', 'löytyi']
  };
  function plural(n, en) {
    var base = String(en).replace(/s$/, '');
    var f = PL[en] || PL[base];
    if (!f) return n + ' ' + en;
    return n + ' ' + (Number(n) === 1 ? f[0] : f[1]);
  }
  var PLNOUN = '(transactions?|purchases?|payments?|months?|days?|times?|lines?|things?|answers?|corrections?|repeating charges?|customers?|people|questions?|figures?|guess(?:es)?|found)';

  var PATTERNS = [
    // counted things
    [new RegExp('^(\\d+) ' + PLNOUN + '$'), function (m, n, w) { return plural(n, w === 'guesses' ? 'guess' : w); }],
    P('From {Q} transaction', '{1} tapahtumasta'),
    P('From {Q} transactions', '{1} tapahtumasta'),
    P('Show all ({Q})', 'Näytä kaikki ({1})'),
    P('More views ({Q})', 'Lisänäkymiä ({1})'),
    P('Showing {Q} of {Q}.', 'Näytetään {1} / {2}.'),
    [/^(\d+) transactions?, (.+?)( \(showing the first (\d+)\))?$/, function (m, n, rest, tail, k) {
      return plural(n, 'transaction') + ', ' + (/^-?€/.test(rest) ? fiMoney(rest) : rest) + (tail ? ' (näytetään ' + k + ' ensimmäistä)' : '');
    }],
    P('{Q} days before payday', '{1} päivää ennen palkkapäivää'),
    P('{Q} corrections', '{1} korjausta'),
    P('a month for {Q} months', 'kuukaudessa {1} kuukauden ajan'),
    P('a month for {Q} month', 'kuukaudessa {1} kuukauden ajan'),
    P('{Q} questions picked for you', '{1} kysymystä valittu sinulle'),
    P('{Q} questions picked for you · {Q} answered', '{1} kysymystä valittu sinulle · {2} vastattu'),
    P('{Q} things in your recent spending', '{1} asiaa viimeaikaisessa kulutuksessasi'),
    P('{Q} thing in your recent spending', '{1} asia viimeaikaisessa kulutuksessasi'),
    P('{Q} people', '{1} henkilöä'),
    P('{Q} customers', '{1} asiakasta'),
    P(' ({Q} customers)', ' ({1} asiakasta)'),
    P('{Q} lines', '{1} riviä'),
    P('Read this receipt ({Q} lines)', 'Lue tämä kuitti ({1} riviä)'),
    P('Read this receipt ({Q} line)', 'Lue tämä kuitti (1 rivi)'),
    P('{Q} lines could not be read as a product.', '{1} riviä ei voitu lukea tuotteeksi.'),
    P('{Q} line could not be read as a product.', '{1} riviä ei voitu lukea tuotteeksi.'),
    P('{Q} personal details were removed first.', '{1} henkilötietoa poistettiin ensin.'),
    P('{Q} personal detail was removed first.', '{1} henkilötieto poistettiin ensin.'),
    P('{N} months', '{1} kuukautta'),
    P('{N} a month', '{1} kuukaudessa'),
    P('{N} a year', '{1} vuodessa'),
    P('{N}% less', '{1} % vähemmän'),
    P('{N}% of income', '{1} % tuloista'),
    P('{N}%', '{1} %'),
    P('{M} a month', '{1} kuukaudessa'),
    P('{M} a week', '{1} viikossa'),
    P('{M} a day', '{1} päivässä'),
    P('{M} a year', '{1} vuodessa'),
    P('{M} more', '{1} enemmän'),
    P('{M} spent', '{1} käytetty'),
    P('{M} left over', '{1} jäi yli'),
    P('{M} more out than in', '{1} enemmän ulos kuin sisään'),
    P('{M} left over · {T}', '{1} jäi yli · {2}'),
    P('{M} more out than in · {T}', '{1} enemmän ulos kuin sisään · {2}'),
    P('{M} spent · {T}', '{1} käytetty · {2}'),
    P('{M} to {M}', '{1} → {2}'),
    P('{M} to {M} a month', '{1} → {2} kuukaudessa'),
    P('{M} of {M}', '{1} / {2}'),
    P('{M} of {M} saved', '{1} / {2} säästetty'),
    P('{M} of {M} saved, by {T}', '{1} / {2} säästetty, {3:by}'),
    P('{M} saved in S-mobiili', '{1} säästetty S-mobiilissa'),
    P('{M} invested in S-mobiili', '{1} sijoitettu S-mobiilissa'),
    P('{N} of {N}', '{1} / {2}'),
    P('{M} over {Q} months.', '{1} {2} kuukaudessa.'),
    P('{M} saved in {Q} months', '{1} säästetty {2} kuukaudessa'),
    P('saved in {Q} months', 'säästetty {1} kuukaudessa'),
    P('{N} months to go.', '{1} kuukautta jäljellä.'),
    P('{N} of {N} characters', '{1} / {2} merkkiä'),
    P('{N} of {N} characters (at least {Q})', '{1} / {2} merkkiä (vähintään {3})'),
    P('{N} of {N} characters (too long)', '{1} / {2} merkkiä (liian pitkä)'),

    P('Claude did not answer: {T}.', 'Claude ei vastannut: {1:t}.'),
    P('A Claude key is saved (ends in {T}).', 'Claude-avain on tallennettu (loppu {1}).'),
    P('A Claude key is saved (ends in {T}). It comes from the environment, so a key saved here is not used until that one is removed.', 'Claude-avain on tallennettu (loppu {1}). Se tulee ympäristöstä, joten tähän tallennettua avainta ei käytetä ennen kuin se poistetaan.'),

    // quiz
    P('Question {Q} of {Q}', 'Kysymys {1} / {2}'),
    P('Question {Q} of {Q} · money skills', 'Kysymys {1} / {2} · rahataidot'),
    P('Question {Q} of {Q} · your money', 'Kysymys {1} / {2} · sinun rahasi'),
    P('Done today: {Q} of {Q} right', 'Tehty tänään: {1} / {2} oikein'),
    P('You guessed {M} too high.', 'Arvauksesi oli {1} liian korkea.'),
    P('You guessed {M} too low.', 'Arvauksesi oli {1} liian matala.'),
    [/^Your guess: (.+?)\. (.*)$/, function (m, g, rest) { return 'Arvauksesi: ' + (/€/.test(g) ? fiMoney(g) : g) + '. ' + tr(rest); }],
    P('Your guess: {M}.', 'Arvauksesi: {1}.'),
    P('Spot on! You were within {M}.', 'Täsmälleen oikein! Olit {1} sisällä.'),
    P('Very close, only {M} too high.', 'Hyvin lähellä, vain {1} liian korkea.'),
    P('Very close, only {M} too low.', 'Hyvin lähellä, vain {1} liian matala.'),
    P('In the ballpark, {M} too high.', 'Suunnilleen oikein, {1} liian korkea.'),
    P('In the ballpark, {M} too low.', 'Suunnilleen oikein, {1} liian matala.'),
    P('Quite far off: you guessed {M} more than the real figure.', 'Aika kaukana: arvasit {1} enemmän kuin todellinen luku.'),
    P('Quite far off: you guessed {M} less than the real figure.', 'Aika kaukana: arvasit {1} vähemmän kuin todellinen luku.'),
    P('How much do you think you spent on {T} this week?', 'Paljonko arvelet käyttäneesi tällä viikolla: {1:cat}?'),
    P('How much do you think you spent on {T} last week?', 'Paljonko arvelet käyttäneesi viime viikolla: {1:cat}?'),
    P('Score saved to Your things: {T}', 'Pisteet tallennettu kohtaan Omat asiasi: {1}'),
    P('Saved to Your things: {T}', 'Tallennettu kohtaan Omat asiasi: {1}'),
    P('Source: {T}', 'Lähde: {1}'),
    P('Start: {T}', 'Aloita: {1}'),

    // greetings and the home page
    P('Hi {T}!', 'Hei {1}!'),
    [/^Hi( .+)?! Ask me anything about your money, or tell me about a goal\. I answer from your own transactions\.$/, function (m, name) {
      return 'Hei' + (name || '') + '! Kysy minulta mitä tahansa rahoistasi tai kerro tavoitteesta. Vastaan omien tapahtumiesi pohjalta.';
    }],
    P('Where your money went in {T}', 'Mihin rahasi menivät {1:inm}'),
    P('Where your money went', 'Mihin rahasi menivät'),
    P('You kept {M} in {T}. What shall we look at?', '{2:inmc} jäi {1} yli. Mitä katsotaan?'),
    P('In {T} {M} more went out than came in. Shall we look at why?', '{1:inmc} meni {2} enemmän kuin tuli. Katsotaanko miksi?'),
    P('Safe to spend until payday on {T}: nothing.', 'Käyttövara palkkapäivään ({1}) asti: ei mitään.'),
    P('Safe to spend until payday on {T}: {M}.', 'Käyttövara palkkapäivään ({1}) asti: {2}.'),
    P('Safe to spend until {T}', 'Käyttövara {1} asti'),
    P('Safe to spend: nothing.', 'Käyttövara: ei mitään.'),
    P('Safe to spend: {M}.', 'Käyttövara: {1}.'),
    P('Your accounts: current account balance {M}', 'Tilisi: käyttötilin saldo {1}'),
    P('S-Bank current account {T}', 'S-Pankin käyttötili {1}'),
    P('{T}, in {Q} days', '{1}, {2} päivän päästä'),
    P('{T}, in {Q} day', '{1}, 1 päivän päästä'),
    P('Delete conversation: {T}', 'Poista keskustelu: {1}'),
    P('Delete "{T}"?', 'Poistetaanko ”{1}”?'),
    P('{T} · not saved', '{1} · ei tallennettu'),
    P('{T}, so far', '{1}, kuluva kuukausi'),
    [/^Today (\d\d:\d\d)$/, 'Tänään $1'],
    [/^Yesterday (\d\d:\d\d)$/, 'Eilen $1'],
    [/^(\d{1,2}) ([A-Z][a-z]{2})(?: (\d{4}))?$/, function (m, d, mon, y) { return enDate(m); }],
    P('Keep in Your things: {T}', 'Tallenna kohtaan Omat asiasi: {1}'),
    P('Explain this text: {T}', 'Selitä tämä teksti: {1}'),

    // baskets
    P('{T}, {M}. Open transactions.', '{1:t}, {2}. Avaa tapahtumat.'),
    P('{T}, {M}. See the transactions.', '{1:t}, {2}. Katso tapahtumat.'),
    P('{T}: bills and things you need every month', '{1}: laskut ja asiat, joita tarvitset joka kuukausi'),
    P('{T}: costs you could not plan for', '{1}: kulut, joihin et voinut varautua'),
    P('{T}: choices you make day to day', '{1}: valinnat, joita teet päivittäin'),
    [/^(.+) · Night out$/, function (m, a) { return a + ' · Ilta ulkona'; }],

    // transactions
    [/^(.+)\. Change category$/, function (m, a) { var p = a.split(', '); p[0] = tr(p[0]); return p.join(', ') + '. Vaihda luokkaa'; }],
    P('Remembered. {Q} purchase updated.', 'Opin tämän. {1} ostos päivitetty.'),
    P('Remembered. {Q} purchases updated.', 'Opin tämän. {1} ostosta päivitetty.'),
    P('Group {Q}', 'Ryhmä {1}'),
    P('Of this, {M} was on nights out.', 'Tästä {1} meni iltoihin ulkona.'),
    P('{Q} found', '{1} löytyi'),

    // check-in
    P('Biggest area: {T}, {M}.', 'Suurin alue: {1:t}, {2}.'),
    P('You spent {M} more than in the period before.', 'Käytit {1} enemmän kuin edellisellä jaksolla.'),
    P('You spent {M} less than in the period before.', 'Käytit {1} vähemmän kuin edellisellä jaksolla.'),
    P('Largest single purchase: {M} on {T} ({T}).', 'Suurin yksittäinen ostos: {1}, {2:date} ({3:t}).'),
    P('Nights out added up to {M}.', 'Illat ulkona kertyivät yhteensä {1}.'),
    P('Your balance was below zero on {Q} days, at worst {M} below zero. Would you like to look at what drove it?', 'Saldosi oli alle nollan {1} päivänä, pahimmillaan {2} alle nollan. Haluatko katsoa, mikä sen aiheutti?'),
    P('Your balance was below zero on {Q} day, at worst {M} below zero. Would you like to look at what drove it?', 'Saldosi oli alle nollan yhtenä päivänä, pahimmillaan {2} alle nollan. Haluatko katsoa, mikä sen aiheutti?'),
    P('Move {M} to your S-Bank savings account?', 'Siirretäänkö {1} S-Pankin säästötilillesi?'),
    P('Move {M} to savings', 'Siirrä {1} säästöön'),
    P('Move {M} to buffer', 'Siirrä {1} puskuriin'),
    P('Set aside {M}', 'Laita {1} sivuun'),
    P('Aim for {M}', 'Tavoitteena {1}'),
    P('You had a {M} surplus {T}. Would you like to set it aside?', 'Sinulle jäi {1} ylimääräistä {2:inm}. Haluatko laittaa sen sivuun?'),
    P('You had {M} left over after spending and saving {T}.', 'Sinulle jäi {1} yli käytön ja säästämisen jälkeen {2:inm}.'),
    P('You can move up to {M} now without touching money needed for bills before payday.', 'Voit siirtää nyt enintään {1} koskematta rahoihin, joita tarvitaan laskuihin ennen palkkapäivää.'),
    P('You can move up to {M} now without touching money for bills.', 'Voit siirtää nyt enintään {1} koskematta laskuihin tarvittaviin rahoihin.'),
    P('Your balance covers about {N} months of regular costs.', 'Saldosi kattaa noin {1} kuukauden perusmenot.'),
    P('Aim for your usual {T} level?', 'Pyritäänkö tavalliseen tasoon: {1:cat}?'),
    P('{T} came to {M} {T}, about {M} more than you usually spend. Would you like to aim for your usual level next time?', '{1:t}: {2} {3:inm}, noin {4} enemmän kuin yleensä. Haluatko tähdätä ensi kerralla tavalliselle tasolle?'),
    P('Your {T} check-in ({T}): you earned {M} and spent {M}.', 'Sinun {1:t}-katsauksesi ({2:inm}): ansaitsit {3} ja käytit {4}.'),

    // money moves
    P('Done: {M} moved to your {W}. It stays in S-mobiili, and you can see it under Your things.', 'Valmis: {1} siirretty {2:dest}. Rahat pysyvät S-mobiilissa, ja näet ne kohdassa Omat asiasi.'),
    P('Done: {M} moved to your {W}.', 'Valmis: {1} siirretty {2:dest}.'),
    P('Move {M} from your current account to your {W}?', 'Siirretäänkö {1} käyttötililtäsi {2:dest}?'),
    P('I offered to move {M} to your {W} here. If you approved it, it is already done. Ask me again for a new offer.', 'Tarjosin tässä {1} siirtoa {2:dest}. Jos hyväksyit sen, se on jo tehty. Pyydä uudestaan, niin teen uuden tarjouksen.'),
    P('to your {W}', '{1:dest}'),
    P('Approve and move {M}', 'Hyväksy ja siirrä {1}'),
    P('Move {M} to your {W}?', 'Siirretäänkö {1} {2:dest}?'),
    P('The smallest amount I can move is {M}.', 'Pienin siirrettävä summa on {1}.'),
    P('I can move at most {M} now: the rest of your balance is needed for bills before payday.', 'Voin siirtää nyt enintään {1}: loput saldostasi tarvitaan laskuihin ennen palkkapäivää.'),
    P('Your balance has changed and {M} is no longer safe to move, so nothing was moved.', 'Saldosi on muuttunut, eikä {1} ole enää turvallista siirtää, joten mitään ei siirretty.'),
    [/^Saved (\d{1,2} [A-Z][a-z]{2} \d{4})$/, function (m, d) { return 'Tallennettu ' + enDate(d); }],

    // afford, cards
    P('{T}: {M}, {Q} purchases', '{1:t}: {2}, {3} ostosta'),
    P('{T}: {M}, {Q} purchase', '{1:t}: {2}, 1 ostos'),
    P('{T} over time', '{1:t} ajan yli'),
    P('Projected balance until payday. {T}', 'Ennustettu saldo palkkapäivään asti. {1:t}'),
    P('lowest balance, {T}', 'alin saldo, {1}'),
    P('on purchases under {M}', 'alle {1} ostoksiin'),
    P('a month on purchases under {M}', 'kuukaudessa alle {1} ostoksiin'),
    P('in total on purchases under {M}', 'yhteensä alle {1} ostoksiin'),
    P('Everyday spending: {M} a week, {M} a day.', 'Arkikulutus: {1} viikossa, {2} päivässä.'),
    P('Everyday spending: {M} a week.', 'Arkikulutus: {1} viikossa.'),
    P('Towards {T}: {M} a month, about {Q} months to go.', 'Kohti tavoitetta {1}: {2} kuukaudessa, noin {3} kuukautta jäljellä.'),
    P('Towards {T}: {M} a month.', 'Kohti tavoitetta {1}: {2} kuukaudessa.'),
    P('{M} by {T}', '{1} {2:by}'),
    P('Higher than {Q}% of the group', 'Korkeampi kuin {1} %:lla ryhmästä'),
    P('Finland on average (Statistics Finland, {Q})', 'Suomi keskimäärin (Tilastokeskus, {1})'),
    P('Finland on average (Statistics Finland)', 'Suomi keskimäärin (Tilastokeskus)'),
    P('Source: Statistics Finland, Paavo ({Q}).', 'Lähde: Tilastokeskus, Paavo ({1}).'),
    P('Source: Statistics Finland, Paavo.', 'Lähde: Tilastokeskus, Paavo.'),
    P('Bonus {N}%: {M}', 'Bonus {1} %: {2}'),
    P('The lines add up to {M}, not the receipt total.', 'Rivit summautuvat arvoon {1}, ei kuitin loppusummaan.'),
    P('At {M} a month, saving the {M} would take over 10 years.', 'Kun säästät {1} kuukaudessa, {2:gen} kerääminen kestäisi yli 10 vuotta.'),
    P('At {M} a month, saving the {M} takes about {Q} months.', 'Kun säästät {1} kuukaudessa, {2:gen} kerääminen kestää noin {3} kuukautta.'),
    P('At {M} a month, saving the {M} takes about {Q} month.', 'Kun säästät {1} kuukaudessa, {2:gen} kerääminen kestää noin kuukauden.'),
    P('For a {M} home: loan {M}, which is {T}. Income looks enough, down payment looks enough.', '{1} kokoiselle kodille: laina {2}, eli {3}. Tulot näyttävät riittävän, omarahoitus näyttää riittävän.'),
    P('For a {M} home: loan {M}, which is {T}. Income looks enough, down payment looks too low.', '{1} kokoiselle kodille: laina {2}, eli {3}. Tulot näyttävät riittävän, omarahoitus näyttää liian pieneltä.'),
    P('For a {M} home: loan {M}, which is {T}. Income looks too low, down payment looks enough.', '{1} kokoiselle kodille: laina {2}, eli {3}. Tulot näyttävät liian pieniltä, omarahoitus näyttää riittävän.'),
    P('For a {M} home: loan {M}, which is {T}. Income looks too low, down payment looks too low.', '{1} kokoiselle kodille: laina {2}, eli {3}. Tulot näyttävät liian pieniltä, omarahoitus näyttää liian pieneltä.'),
    P('{N} days before payday', '{1} päivää ennen palkkapäivää'),
    P('balance before {M}', 'saldo ennen: {1}'),
    P('{T}: balance before {M}', '{1}: saldo ennen {2}'),
    P('{T}: {Q} days before payday', '{1}: {2} päivää ennen palkkapäivää'),
    P('Please paste between {Q} and {T} characters of text.', 'Liitä tekstiä {1}–{2} merkkiä.'),
    P('You asked me to remember this. I keep it in mind when I answer.', 'Pyysit minua muistamaan tämän. Pidän sen mielessä vastatessani.'),
    P('You asked me to remember this {T}. I keep it in mind when I answer.', 'Pyysit minua muistamaan tämän ({1:when}). Pidän sen mielessä vastatessani.'),
    P('Kept {T}. The figures are from that day.', 'Tallennettu {1:when}. Luvut ovat tuolta päivältä.'),
    P('{N}% of the goal', '{1} % tavoitteesta'),
    P('Forget: {T} is {T}', 'Unohda: {1:t} → {2:t}'),
    P('Forget: {T}', 'Unohda: {1}'),
    P('Customer {Q}', 'Asiakas {1}'),
    P('{T}, night out', '{1:t}, ilta ulkona'),
    P('{N} figures, each filled in by code from your data. Tap one to see where it comes from.', '{1} lukua, jotka koodi on täyttänyt tiedoistasi. Napauta yhtä nähdäksesi, mistä se tulee.'),
    [/^(\d+) figures, each filled in by code from your data\. Tap one to see where it comes from\.$/, function (m, n) { return n + ' lukua, jotka koodi on täyttänyt tiedoistasi. Napauta yhtä nähdäksesi, mistä se tulee.'; }],
    P('{T} is an estimate for {T}', '{1} on arvio: {2}'),
    P('{T} is an estimate', '{1} on arvio'),

    // extras.js periods
    [new RegExp('^(' + EN_MONTHS.join('|') + ') (\\d{4})$'), function (m, mon, y) { return MON_NOM[EN_MONTHS.indexOf(mon)] + ' ' + y; }],
    [/^(\d{1,2}) ([A-Z][a-z]{2})(?: (\d{4}))? to (\d{1,2}) ([A-Z][a-z]{2}) (\d{4})$/, function (m, d1, m1, y1, d2, m2, y2) {
      return d1 + '.' + (EN_MON3.indexOf(m1) + 1) + '.' + (y1 || '') + '–' + d2 + '.' + (EN_MON3.indexOf(m2) + 1) + '.' + y2;
    }]
  ];

  // Strings of the "English => Suomi" lines; a key may itself contain " => " never.
  var MAP = {};
  LINES.forEach(function (line) {
    var i = line.indexOf(' => ');
    if (i > 0) MAP[line.slice(0, i)] = line.slice(i + 4);
  });
  window.SvI18n.add(MAP, PATTERNS);
  if (window.SvI18n._test) window.SvI18n._test.fiMoney = fiMoney;
})();
