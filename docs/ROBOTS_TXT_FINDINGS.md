# Robots.txt findings — major Indian airlines

Checked live (via web search + fetch, not simulated) on 2026-09-05.
This directly informs which paths `airline_adapter_template.py`
subclasses must NOT hit, per spec sections 2 & 12.

## IndiGo (goindigo.in) — CHECKED

Full file: `https://www.goindigo.in/robots.txt`

Directly relevant disallows for a fare-search adapter:
```
Disallow: /booking/*
Disallow: /book/*
Disallow: /content/indigo/in/en/booking/*
Disallow: /content/indigo/in/en/book/*
Disallow: /check-in/*
Disallow: /content/indigo/in/en/check-in/*
Disallow: /search.html
```
**Conclusion: the booking/search flow (where fare results render) is
explicitly disallowed.** A compliant adapter cannot crawl IndiGo's own
search results pages at all. A real IndiGo adapter would need either a
legitimate partner/affiliate data feed, or to be dropped entirely for
this source — not built by crawling `/booking/*`.

## Air India Express (airindiaexpress.com) — CHECKED

Full file: `https://www.airindiaexpress.com/robots.txt`

```
Disallow: /flight-availability
Disallow: /retro-claim
Disallow: /loyalty-addon-packs
Disallow: /dam
Disallow: /content/dam
```
**Conclusion: `/flight-availability` — almost certainly the fare-search
results path — is explicitly disallowed.** Same conclusion as IndiGo:
not scrapable in compliance with their robots.txt.

## SpiceJet (spicejet.com) — CHECKED

Full file: `https://www.spicejet.com/robots.txt`

```
Disallow: /cgi-bin/
Disallow: https://www.spicejet.com/api/v1
Disallow: https://www.spicejet.com/public/
Disallow: https://www.spicejet.com/externalBooking
```
**Conclusion: their own API (`/api/v1`) and `/externalBooking` path are
explicitly disallowed for bots.** Not scrapable in compliance with
their robots.txt.

## Air India (airindia.com / airindia.in) — CHECKED (unreachable)

Re-verified live with real curl on 2026-09-06: both
`https://www.airindia.com/robots.txt` and
`https://www.airindia.in/robots.txt` return **HTTP 000 (no response)** —
from both the `AirIndexIndiaBot/1.0` UA and a full browser UA. The edge
CDN/anti-bot layer (Akamai/CloudFront-style) refuses to serve even the
robots.txt to non-browser connections. **Conclusion: Air India is
effectively scrape-blocked at the network edge; a compliant adapter
cannot even fetch `/robots.txt`, so treat the site as offline for the
adapter** (SOURCE UNAVAILABLE), and only integrate via a legitimate
partner/affiliate feed if one is ever available.

## Akasa Air (akasaair.com) — CHECKED

Re-verified live with real curl on 2026-09-06:
`https://www.akasaair.com/robots.txt` returns **HTTP 200** and is
robots-PERMISSIVE on the surface:

```
User-Agent: *
Sitemap: https://www.akasaair.com/sitemap.xml
Sitemap: https://www.akasaair.com/book-flight-tickets/sitemap_index.xml
```

No `Disallow:` rules at all (the `*` group implies allow-everything).
Caveat: a permissive robots.txt does not guarantee the fare-search flow
isn't behind CAPTCHA/anti-bot protection — the adapter template's
"never attempt to bypass CAPTCHA/login walls" rule still applies — but
unlike IndiGo/Air India Express/SpiceJet there is no explicit robots
disallow of the booking path.

## Overall implication for this project

Three of the five airlines named in the spec (IndiGo, Air India
Express, SpiceJet) **disallow bot access to exactly the pages a fare
adapter would need** (their booking/search-results flow). This is a
real, structural finding, not a hypothetical caveat:

- It strongly suggests the "automated web scraping of airline
  portals" approach will hit the same wall on
  every major carrier's own site, since booking flows are precisely
  what airlines have the strongest incentive to keep bot-free (fraud,
  scalping, server load from fare-shopping bots).
- The practical path per spec section 2 ("permitted online travel
  aggregator portals") is more likely to run through **OTA
  partner/affiliate APIs** (many OTAs offer official fare-search APIs
  for partners) or **public datasets** (DGCA's own published fare/
  traffic statistics) than through direct airline-site scraping.
- This doesn't block the platform — the DemoAdapter and the
  `SOURCE_UNAVAILABLE` handling exist precisely so the system keeps
  working when live sources can't be used — but it does mean "add a
  real IndiGo/SpiceJet/Air India Express adapter" is a smaller task
  than it looks (there's likely nothing legally scrapable to adapt to
  on their own sites), and the team's ingestion effort is better spent
  on official APIs and DGCA public data than on more scraper code.
