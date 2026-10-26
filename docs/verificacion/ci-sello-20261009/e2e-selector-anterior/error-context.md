# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: session-persistence.spec.ts >> cada cuenta conserva sus casos y Alice recupera su corrida tras reiniciar
- Location: e2e\session-persistence.spec.ts:110:5

# Error details

```
Test timeout of 90000ms exceeded.
```

```
Error: locator.click: Test timeout of 90000ms exceeded.
Call log:
  - waiting for getByRole('dialog', { name: 'Nuevo caso' }).getByRole('button', { name: 'Crear caso' })

```

# Page snapshot

```yaml
- generic [ref=e1]:
  - navigation [ref=e2]:
    - generic [ref=e3]:
      - button "OPCIONES" [ref=e5] [cursor=pointer]
      - generic [ref=e10]:
        - link "Preparación" [ref=e11] [cursor=pointer]:
          - /url: /preparacion
        - link "MolcyBeta" [ref=e12] [cursor=pointer]:
          - /url: /molcy
        - link "Batch" [ref=e13] [cursor=pointer]:
          - /url: /evaluation/batch
      - link "MolDesign — ir al inicio" [ref=e14] [cursor=pointer]:
        - /url: /
        - img "Logo de MolDesign" [ref=e15]
      - generic [ref=e16]:
        - link "EVALUACIÓN" [ref=e17] [cursor=pointer]:
          - /url: /evaluation
        - link "Moldex" [ref=e18] [cursor=pointer]:
          - /url: /moldex
        - link "HISTORIAL" [ref=e19] [cursor=pointer]:
          - /url: /history
      - generic [ref=e20]:
        - button "Actividad" [ref=e22]
        - generic [ref=e26]: alice
        - button "SALIR" [ref=e27] [cursor=pointer]
  - main [ref=e28]:
    - generic [ref=e31]:
      - generic [ref=e32]:
        - navigation "Casos" [ref=e34]:
          - generic [ref=e35]:
            - heading "Casos" [level=2] [ref=e36]
            - button "Nuevo caso" [ref=e37]
            - button "Ocultar el panel de casos" [expanded] [ref=e39]
          - generic [ref=e43]:
            - generic [ref=e44]: Buscar casos
            - searchbox "Buscar casos" [ref=e46]
          - paragraph [ref=e48]: Todavía no hay casos.
        - separator "Ancho del panel de casos" [ref=e49]
      - main [ref=e50]:
        - generic [ref=e52]:
          - heading "Crea un caso de estudio" [level=1] [ref=e53]
          - paragraph [ref=e54]: Reúne una proteína, una hipótesis de sitio, ligandos, corridas, controles e informes en un espacio reproducible.
          - generic [ref=e55]:
            - button "Crear un caso" [ref=e56]
            - button "Abrir carpeta existente" [disabled] [ref=e58]
          - paragraph [ref=e61]: Abrir una carpeta del disco requiere la aplicación de escritorio. En el navegador los casos se guardan localmente en este equipo.
          - paragraph [ref=e62]: Guardado en este navegador
      - dialog [ref=e64]:
        - generic [ref=e65]:
          - generic [ref=e66]:
            - heading "Nuevo caso" [level=2] [ref=e67]
            - paragraph [ref=e68]: Las preguntas científicas se responden después, en «Detalles del caso». Aquí sólo lo mínimo.
          - button "Cerrar" [ref=e69]
        - generic [ref=e73]:
          - generic [ref=e74]:
            - generic [ref=e75]: Nombre
            - textbox "Nombre" [active] [ref=e76]:
              - /placeholder: p. ej. Serie de inhibidores — cribado inicial
              - text: Caso de Alice
          - group "Tipo aproximado" [ref=e77]:
            - generic [ref=e79]:
              - generic [ref=e80] [cursor=pointer]:
                - radio "Explorar una hipótesis" [checked] [ref=e81]
                - text: Explorar una hipótesis
              - generic [ref=e82] [cursor=pointer]:
                - radio "Comparar una serie" [ref=e83]
                - text: Comparar una serie
              - generic [ref=e84] [cursor=pointer]:
                - radio "Revisar una pose" [ref=e85]
                - text: Revisar una pose
              - generic [ref=e86] [cursor=pointer]:
                - radio "Preparar evidencia para un cálculo posterior" [ref=e87]
                - text: Preparar evidencia para un cálculo posterior
          - generic [ref=e88]:
            - generic [ref=e89]: Ubicación
            - paragraph [ref=e90]: Guardado en este navegador
          - generic [ref=e91]:
            - button "Cancelar" [ref=e92]
            - button "Crear un caso" [ref=e93]
  - button "Abrir MolChat" [ref=e94] [cursor=pointer]
  - alert [ref=e98]
```

# Test source

```ts
  1   | import { expect, test, type Page, type Route } from "@playwright/test";
  2   |
  3   | type Researcher = "alice" | "bob";
  4   |
  5   | const API = "http://127.0.0.1:8999";
  6   |
  7   | function authFor(user: Researcher) {
  8   |   return {
  9   |     token: `token-${user}`,
  10  |     refreshToken: `refresh-${user}`,
  11  |     user: { user_id: user, username: user, email: `${user}@local.test` },
  12  |   };
  13  | }
  14  |
  15  | async function switchSession(page: Page, user: Researcher) {
  16  |   await page.evaluate((auth) => localStorage.setItem("moldesign_auth", JSON.stringify(auth)), authFor(user));
  17  |   await page.reload({ waitUntil: "domcontentloaded" });
  18  |   await expect(page.getByRole("heading", { name: "Casos", exact: true })).toBeVisible();
  19  | }
  20  |
  21  | async function createCase(page: Page, name: string) {
  22  |   await page.getByRole("button", { name: /crear caso|nuevo caso/i }).first().click();
  23  |   const dialog = page.getByRole("dialog", { name: "Nuevo caso" });
  24  |   await dialog.getByLabel("Nombre").fill(name);
> 25  |   await dialog.getByRole("button", { name: "Crear caso" }).click();
      |                                                            ^ Error: locator.click: Test timeout of 90000ms exceeded.
  26  |   await expect(dialog).toBeHidden();
  27  |   await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
  28  | }
  29  |
  30  | function persistedResult() {
  31  |   return {
  32  |     id: "result-alice",
  33  |     molecule_id: "molecule-alice",
  34  |     smiles_hash: "sha256:alice",
  35  |     target_name: "Receptor persistido",
  36  |     target_spearman_rho: null,
  37  |     target_pdb_id: "7E2Y",
  38  |     affinity_kcal: -8.4,
  39  |     affinity_score: 84,
  40  |     docking_poses: [{ rank: 1, affinity: -8.4, rmsd_lb: 0, rmsd_ub: 0 }],
  41  |     parsing_source: "sdf",
  42  |     vina_version: "test",
  43  |     vina_random_seed: 42,
  44  |     scientific_warnings: [],
  45  |     task_id: "task-alice",
  46  |     molecular_weight: 46.07,
  47  |     log_p: -0.3,
  48  |     tpsa: 20.2,
  49  |     hbd: 1,
  50  |     hba: 1,
  51  |     rotatable_bonds: 0,
  52  |     heavy_atom_count: 3,
  53  |     ring_count: 0,
  54  |     lipinski_pass: true,
  55  |     veber_pass: true,
  56  |     ghose_pass: null,
  57  |     egan_pass: null,
  58  |     muegge_pass: null,
  59  |     muegge_score: null,
  60  |     fsp3: null,
  61  |     is_pains: false,
  62  |     pains_matches: [],
  63  |     qed: 0.4,
  64  |     sa_score: 1.2,
  65  |     sa_reasons: [],
  66  |     adme_score: null,
  67  |     druglikeness_score: null,
  68  |     blood_viability_score: null,
  69  |     total_score: 84,
  70  |     gnn_score: null,
  71  |     xgb_score: null,
  72  |     clgnn_score: null,
  73  |     quantum_score: null,
  74  |     ums_score: null,
  75  |     mmgbsa_score: null,
  76  |     target_family: null,
  77  |     engine_used: "vina",
  78  |     fallback_reason: null,
  79  |     in_applicability_domain: true,
  80  |     model_used: "vina",
  81  |     specificity_score: null,
  82  |     hotspots_hit: [],
  83  |     target_hotspots: [],
  84  |     shap_values: null,
  85  |     gnn_attention: null,
  86  |     gnn_attention_svg: null,
  87  |     gnn_pharmacophores: null,
  88  |     selectivity_ratio: null,
  89  |     selectivity_verdict: null,
  90  |     anti_target_results: [],
  91  |     selectivity_ran: false,
  92  |     poses_file_path: null,
  93  |     is_control: false,
  94  |     ai_report: null,
  95  |     blockchain_tx_id: null,
  96  |     error_message: null,
  97  |     evaluated_at: "2026-08-27T12:00:00.000Z",
  98  |   };
  99  | }
  100 |
  101 | async function json(route: Route, body: unknown, status = 200) {
  102 |   await route.fulfill({
  103 |     status,
  104 |     contentType: "application/json",
  105 |     headers: { "Access-Control-Allow-Origin": "http://127.0.0.1:3100" },
  106 |     body: JSON.stringify(body),
  107 |   });
  108 | }
  109 |
  110 | test("cada cuenta conserva sus casos y Alice recupera su corrida tras reiniciar", async ({ page }) => {
  111 |   // La sesión debe existir antes de que React hidrate AuthProvider. Inyectarla
  112 |   // después de la primera carga deja al provider con un snapshot obsoleto y no
  113 |   // reproduce un arranque real de la aplicación.
  114 |   await page.addInitScript((auth) => {
  115 |     if (!localStorage.getItem("moldesign_auth")) {
  116 |       localStorage.setItem("moldesign_auth", JSON.stringify(auth));
  117 |     }
  118 |   }, authFor("alice"));
  119 |
  120 |   const authorization: string[] = [];
  121 |   await page.route(`${API}/**`, async (route) => {
  122 |     const request = route.request();
  123 |     const path = new URL(request.url()).pathname;
  124 |     const bearer = request.headers().authorization;
  125 |     if (bearer) authorization.push(`${path}:${bearer}`);
```
