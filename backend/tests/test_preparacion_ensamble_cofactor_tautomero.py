"""Tres veredictos falsos de Preparación, medidos con Vina real el 2026-10-10.

1. **Ensamble.** Toda corrida con K > 1 salía BLOQUEADA por «faltan cuatro hashes» y
   «no conservó el archivo de poses»: cada conformación los guarda en
   `execution_provenance.por_conformacion` y la auditoría sólo leía el nivel superior
   (3F75 + paracetamol, K = 3).
2. **Cofactor declarado ligando del cristal.** 21 entradas del catálogo declaran un
   cofactor como ligando del sitio (hemo en COX-1/2 y CYP2D6, NADP en 3SRW, FMN…). La
   preparación lo retira como si fuera el ligando y la auditoría decía «ningún cofactor
   retirado» (3SRW + trimetoprim: el NADP desapareció en silencio).
3. **Tautómero cambiado.** El modo por defecto acopla el canónico de RDKit, que pasa el
   hidroxamato de vorinostat a iminol; la auditoría lo mezclaba con el aviso genérico de
   «varios candidatos», el mismo que da la aspirina.
"""

from __future__ import annotations

import copy

import pytest

from chem.declaracion_tautomeros import declarar_tautomeros
from core.i18n_plantillas import _PARECE_CASTELLANO
from services.dossier import preparacion
from services.dossier.localization import traducir_dossier
from services.docking.preparer import ORGANIC_COFACTORS_KEPT
from tests.test_diff_de_especies_de_la_corrida import _diff
from tests.test_preparacion_auditoria import _auditar, _con_procedencia, _requisito

_LIGANDO = ("ligand_input_sha256", "ligand_pdbqt_sha256", "poses_sha256", "log_sha256")


def _sin_espanol(auditoria: dict, clave: str) -> None:
    """La auditoría en inglés no deja castellano en lo que enseña este requisito."""
    requisito = _requisito(traducir_dossier(auditoria, "en"), clave)
    for campo in ("valor", "razon", "accion_recomendada"):
        texto = requisito.get(campo)
        if isinstance(texto, str):
            assert not _PARECE_CASTELLANO.search(texto), (campo, texto)


# ── 1 · Ensamble ─────────────────────────────────────────────────────


def _ensamble(k: int = 3, *, sin: dict[int, str] | None = None) -> dict:
    caso = _con_procedencia(_diff())
    resultado = caso["eval_result"]
    procedencia = copy.deepcopy(resultado.docking_protocol["execution_provenance"])
    for clave in _LIGANDO:
        procedencia.pop(clave)
    procedencia["por_conformacion"] = []
    for indice in range(k):
        fila = {"indice": indice, "poses_file_path": f"runs/docking/x__c{indice:02d}/poses.sdf",
                **{clave: f"{indice}{clave[0]}" * 32 for clave in _LIGANDO}}
        if sin and indice in sin:
            fila.pop(sin[indice])
        procedencia["por_conformacion"].append(fila)
    resultado.docking_protocol = {**resultado.docking_protocol, "execution_provenance": procedencia}
    resultado.poses_file_path = None
    return caso


class TestEnsamble:
    def test_con_todos_los_hashes_por_conformacion_no_bloquea(self):
        auditoria = _auditar(_ensamble())
        origen = _requisito(auditoria, "pose.origen")
        hashes = _requisito(auditoria, "procedencia.hashes")
        assert origen["estado"] == "REGISTRADO"
        assert origen["valor"].startswith("3 SDF de poses, uno por conformación: #0 SHA-256 ")
        assert hashes["estado"] == "REGISTRADO"
        assert hashes["valor"] == "5/5 registrados en cada una de las 3 conformaciones"
        assert not {"pose.origen", "procedencia.hashes"} & set(auditoria["bloqueantes"])

    def test_una_conformacion_sin_log_lo_nombra(self):
        auditoria = _auditar(_ensamble(sin={2: "log_sha256"}))
        hashes = _requisito(auditoria, "procedencia.hashes")
        assert hashes["estado"] == "NO_DISPONIBLE"
        assert hashes["razon"] == "Faltan: log_sha256 (#2)"
        assert "procedencia.hashes" in auditoria["bloqueantes"]
        # Las poses siguen enteras: el bloqueo es por el log, no por ellas.
        assert _requisito(auditoria, "pose.origen")["estado"] == "REGISTRADO"

    def test_una_conformacion_sin_poses_bloquea_su_origen(self):
        auditoria = _auditar(_ensamble(sin={1: "poses_sha256"}))
        origen = _requisito(auditoria, "pose.origen")
        assert origen["estado"] == "NO_DISPONIBLE"
        assert origen["razon"] == "Falta el archivo de poses o su hash en la(s) conformación(es) #1."
        assert "pose.origen" in auditoria["bloqueantes"]

    def test_una_corrida_de_una_sola_no_cambia(self):
        """Control: sin `por_conformacion` se lee el nivel superior, como siempre."""
        auditoria = _auditar(_con_procedencia(_diff()))
        assert _requisito(auditoria, "procedencia.hashes")["valor"] == "5/5 registrados"
        assert _requisito(auditoria, "pose.origen")["valor"] == "SDF SHA-256 " + "3" * 64

    @pytest.mark.parametrize("sin", [None, {2: "log_sha256"}, {1: "poses_sha256"}])
    def test_sale_en_ingles(self, sin):
        auditoria = _auditar(_ensamble(sin=sin))
        _sin_espanol(auditoria, "pose.origen")
        _sin_espanol(auditoria, "procedencia.hashes")


# ── 2 · Cofactor declarado ligando del cristal ───────────────────────


def _con_ligando_del_cristal(nombre: str, *, con_metal: bool = False) -> dict:
    """El diff del fixture con el ligando del sitio renombrado y, salvo que se pida, sin metales."""
    diff = _diff()
    cerca = diff["near_site"]
    cerca["removed"] = [f for f in cerca["removed"]
                        if f["category"] in ("water", "site_ligand") or (con_metal and f["category"] == "metal")]
    for fila in cerca["removed"]:
        if fila["category"] == "site_ligand":
            fila["name"] = nombre
    diff["site_ligand"] = nombre
    return _con_procedencia(diff)


class TestCofactorComoLigandoDelCristal:
    def test_el_nadp_retirado_como_ligando_bloquea_y_se_nombra(self):
        auditoria = _auditar(_con_ligando_del_cristal("NAP"))
        metales = _requisito(auditoria, "entorno.metales_cofactores")
        assert metales["estado"] == "ABSTENCION"
        assert metales["valor"] == "Cofactor retirado como ligando del cristal: NAP A:601 (0.0 Å)."
        assert "no lo desplaza" in metales["razon"]
        assert "con el cofactor dentro" in metales["accion_recomendada"]
        assert "entorno.metales_cofactores" in auditoria["bloqueantes"]
        assert auditoria["estado"] == "BLOQUEADO"

    def test_el_hemo_tambien(self):
        metales = _requisito(_auditar(_con_ligando_del_cristal("HEM")), "entorno.metales_cofactores")
        assert metales["estado"] == "ABSTENCION"

    def test_el_atp_lo_desplaza_un_competitivo_y_pide_revision(self):
        auditoria = _auditar(_con_ligando_del_cristal("ATP"))
        metales = _requisito(auditoria, "entorno.metales_cofactores")
        assert metales["estado"] == "REVISAR"
        assert metales["valor"] == "Cofactor retirado como ligando del cristal: ATP A:601 (0.0 Å)."
        assert "inhibidor competitivo" in metales["razon"]
        assert "entorno.metales_cofactores" in auditoria["en_revision"]
        assert "entorno.metales_cofactores" not in auditoria["bloqueantes"]

    def test_con_un_metal_retirado_se_nombran_los_dos(self):
        metales = _requisito(_auditar(_con_ligando_del_cristal("NAP", con_metal=True)),
                             "entorno.metales_cofactores")
        assert metales["estado"] == "ABSTENCION"
        assert metales["valor"] == ("Retirados a 6 Å o menos: ZN A:301 (0.0 Å). "
                                    "Cofactor retirado como ligando del cristal: NAP A:601 (0.0 Å).")

    def test_un_ligando_que_no_es_cofactor_no_cambia(self):
        """Control: retirar el ligando del cristal es el objeto de la corrida."""
        metales = _requisito(_auditar(_con_ligando_del_cristal("LIG")), "entorno.metales_cofactores")
        assert metales["estado"] == "REGISTRADO"
        assert metales["valor"] == "Ninguno retirado a 6 Å o menos"
        assert "accion_recomendada" not in metales

    def test_los_no_desplazables_son_cofactores_que_el_producto_conserva(self):
        assert preparacion._COFACTORES_NO_DESPLAZABLES <= ORGANIC_COFACTORS_KEPT

    @pytest.mark.parametrize("nombre, con_metal", [("NAP", False), ("ATP", False), ("NAP", True)])
    def test_sale_en_ingles(self, nombre, con_metal):
        _sin_espanol(_auditar(_con_ligando_del_cristal(nombre, con_metal=con_metal)), "entorno.metales_cofactores")


# ── 3 · Tautómero cambiado respecto a la entrada ─────────────────────


def _tautomeria(entrada: str, acoplado: str, *, modo: str = "canonico") -> dict:
    declaracion_entrada = declarar_tautomeros(entrada)
    declaracion_entrada["tautomero_acoplado"] = "entrada" if modo == "entrada" else "canonico_rdkit"
    return {"aplicada": modo != "entrada", "modo": modo, "alternativas": declaracion_entrada["n_candidatos"],
            "declaracion_entrada": declaracion_entrada, "declaracion": declarar_tautomeros(acoplado)}


VORINOSTAT = "O=C(CCCCCCC(=O)Nc1ccccc1)NO"
VORINOSTAT_IMINOL = "O=C(CCCCCCC(O)=NO)Nc1ccccc1"


ACICLOVIR = "Nc1nc2n(COCCO)cnc2c(=O)[nH]1"
ACICLOVIR_N3H = "Nc1nc(=O)c2ncn(COCCO)c2[nH]1"


class TestTautomeroCambiado:
    def test_el_iminol_de_vorinostat_bloquea_y_recomienda_lo_escrito(self):
        """El canónico de RDKit lo pasó a iminol: forma sin población, aunque la eligiera MolDesign."""
        auditoria = _auditar(_con_procedencia(_diff(), tautomeria=_tautomeria(VORINOSTAT, VORINOSTAT_IMINOL)))
        tautomero = _requisito(auditoria, "ligando.tautomero")
        assert tautomero["estado"] == "ABSTENCION"
        assert tautomero["valor"] == (f"Forma minoritaria acoplada: {VORINOSTAT_IMINOL} "
                                      "(amida o hidroxamato como ácido imídico (iminol))")
        assert tautomero["razon"].startswith("Se acopló el tautómero canónico de RDKit")
        assert tautomero["accion_recomendada"].endswith("el tautómero que escribiste es la forma mayoritaria.")
        assert tautomero["reevaluar"] == [{"tautomero": "entrada", "smiles": VORINOSTAT}]
        assert "ligando.tautomero" in auditoria["bloqueantes"]

    def test_un_cambio_a_otra_forma_plausible_pide_revision(self):
        """Aciclovir: el canónico mueve el H de N1 a N3; las dos son lactamas y ninguna regla decide."""
        tautomero = _requisito(_auditar(_con_procedencia(_diff(), tautomeria=_tautomeria(ACICLOVIR, ACICLOVIR_N3H))),
                               "ligando.tautomero")
        assert tautomero["estado"] == "REVISAR"
        assert tautomero["valor"].startswith("Entrada ")
        assert "Por defecto (conservar el tautómero que escribí)" in tautomero["accion_recomendada"]
        assert tautomero["reevaluar"] == [{"tautomero": "entrada", "smiles": ACICLOVIR}]

    def test_la_aspirina_ya_no_es_multiestado(self):
        """Su otro candidato es el enol del éster: forma minoritaria conocida, no un estado a revisar."""
        aspirina = "CC(=O)Oc1ccccc1C(=O)O"
        tautomero = _requisito(_auditar(_con_procedencia(_diff(), tautomeria=_tautomeria(aspirina, aspirina))),
                               "ligando.tautomero")
        assert tautomero["estado"] == "REGISTRADO"
        assert tautomero["razon"].endswith(
            "Los demás candidatos de RDKit (1) son formas minoritarias conocidas: enol de un carbonilo sin conjugar.")
        assert "accion_recomendada" not in tautomero
        assert "reevaluar" not in tautomero

    def test_la_e_z_de_la_entacapona_no_cuenta_como_cambio(self):
        """La declaración borra la E/Z del sistema tautomérico; el hidrógeno no se movió."""
        entacapona = "CCN(CC)C(=O)/C(=C/c1cc(O)c(O)c([N+](=O)[O-])c1)C#N"
        tautomero = _requisito(_auditar(_con_procedencia(_diff(), tautomeria=_tautomeria(entacapona, entacapona))),
                               "ligando.tautomero")
        assert "accion_recomendada" not in tautomero

    def test_el_hidroxamato_escrito_queda_registrado(self):
        tautomero = _requisito(
            _auditar(_con_procedencia(_diff(), tautomeria=_tautomeria(VORINOSTAT, VORINOSTAT, modo="entrada"))),
            "ligando.tautomero")
        assert tautomero["estado"] == "REGISTRADO"
        assert "accion_recomendada" not in tautomero
        assert "tautómero del usuario" in tautomero["razon"]

    def test_un_tautomero_del_usuario_sin_poblacion_bloquea_y_recomienda_el_mayoritario(self):
        """Petición del propietario: si lo escrito no es viable, se dice y se propone la forma mayoritaria."""
        auditoria = _auditar(_con_procedencia(_diff(), tautomeria=_tautomeria("Oc1ccccn1", "Oc1ccccn1", modo="entrada")))
        tautomero = _requisito(auditoria, "ligando.tautomero")
        assert tautomero["estado"] == "ABSTENCION"
        assert "hidroxiazina en vez de su forma oxo" in tautomero["valor"]
        assert "tautómero del usuario" in tautomero["razon"]
        assert tautomero["accion_recomendada"] == "Vuelve a evaluar con la forma mayoritaria: O=c1cccc[nH]1"
        # La forma mayoritaria se acopla tal cual: nunca se propone el canónico de RDKit.
        assert tautomero["reevaluar"] == [{"tautomero": "entrada", "smiles": "O=c1cccc[nH]1"}]

    def test_varios_estados_reales_siguen_en_revision(self):
        """Acetilacetona: ceto y enol conjugado pesan los dos; ninguna regla descarta ninguno."""
        acac = "CC(=O)CC(C)=O"
        tautomero = _requisito(_auditar(_con_procedencia(_diff(), tautomeria=_tautomeria(acac, acac, modo="entrada"))),
                               "ligando.tautomero")
        assert tautomero["estado"] == "REVISAR"

    @pytest.mark.parametrize("entrada, acoplado, modo", [
        (VORINOSTAT, VORINOSTAT_IMINOL, "canonico"),
        ("CC(=O)Oc1ccccc1C(=O)O", "CC(=O)Oc1ccccc1C(=O)O", "entrada"),
        ("Oc1ccccn1", "Oc1ccccn1", "entrada"),
        (ACICLOVIR, ACICLOVIR_N3H, "canonico"),
    ])
    def test_sale_en_ingles(self, entrada, acoplado, modo):
        auditoria = _auditar(_con_procedencia(_diff(), tautomeria=_tautomeria(entrada, acoplado, modo=modo)))
        _sin_espanol(auditoria, "ligando.tautomero")
        # Lo que se reevalúa son datos: el modo y el SMILES no se traducen.
        en = _requisito(traducir_dossier(auditoria, "en"), "ligando.tautomero")
        assert en.get("reevaluar") == _requisito(auditoria, "ligando.tautomero").get("reevaluar")


# ── 4 · Las reglas de forma minoritaria ──────────────────────────────


@pytest.mark.parametrize("smiles, plausibles", [
    ("CC(=O)Oc1ccccc1C(=O)O", 1),          # aspirina
    ("CC(=O)Nc1ccc(O)cc1", 1),             # paracetamol: formas ceto del fenol y amida-iminol
    ("CC(C)=O", 1),                        # acetona
    (VORINOSTAT, 1),                       # iminol y nitroso descartados
    ("COCCOc1cc2ncnc(Nc3cccc(c3)C#C)c2cc1OCCOC", 1),   # erlotinib: iminas exocíclicas
    ("O=c1[nH]cc(F)c(=O)[nH]1", 1),        # 5-fluorouracilo: lactimas
    ("CC(=O)CC(C)=O", 2),                  # acetilacetona: el enol conjugado pesa
    (ACICLOVIR, 2),                        # N1-H y N3-H
    ("CN1C(C(=O)Nc2ccccn2)=C(O)c2ccccc2S1(=O)=O", 3),  # piroxicam: enol vinílogo
])
def test_cuantos_candidatos_quedan(smiles, plausibles):
    from chem.tautomeros_minoritarios import clasificar
    candidatos = [c["smiles"] for c in declarar_tautomeros(smiles)["candidatos"]]
    assert sum(1 for reglas in clasificar(candidatos).values() if not reglas) == plausibles
