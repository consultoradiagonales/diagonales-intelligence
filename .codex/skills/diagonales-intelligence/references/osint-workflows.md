# OSINT Workflows

## Public-Source Boundary

Use legal, public-source research only. Prefer official registries, government portals, public search engines, public social profiles, news, official documents, and archived public pages.

Do not instruct users to bypass access controls, scrape private accounts, evade rate limits, dox private individuals, or use leaked credentials/data.

## Identity Radiografia

For DNI/CUIL/CUIT:

1. Normalize with `normalizar_identificador`.
2. If input is DNI, derive CUIL/CUIT variants using AFIP modulo 11.
3. Query BCRA for up to the first derived CUILs.
4. Classify credit risk with `clasificar_riesgo`.
5. Generate search dorks with `generar_dorks(nombre, cuil_principal)`.
6. Save query results only through existing database models when working inside the API.

## Dork Categories

Use these categories consistently:

- `general`: broad person/company context.
- `judiciales`: PJN, CSJN, JusBaires, judicial cause terms.
- `patrimoniales`: Boletin Oficial, compras, licitaciones, contrataciones.
- `redes_sociales`: X, Instagram, Facebook, LinkedIn.
- `medios`: Infobae, Clarin, La Nacion, Pagina/12 and other news portals.
- `empresas`: CUIT, sociedades, directorio, corporate traces.
- `dominios`: domain, WHOIS, `.ar`, institutional web footprint.

## Web Frontend Behavior

The OSINT frontend should:

- Accept `consulta`, `tipo`, and optional `identificador`.
- Use `/api/osint/busqueda` when a backend URL is available.
- Fall back to static Google dork generation when hosted on GitHub Pages without API.
- Open results in new tabs and avoid pretending it has fetched external search results directly.

## Reporting

When presenting OSINT results, distinguish:

- Directly observed facts from a source.
- Dorks/search leads that still require analyst review.
- Inferences from multiple sources.
- Missing or inconclusive evidence.
