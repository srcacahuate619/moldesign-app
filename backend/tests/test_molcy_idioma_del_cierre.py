import json,uuid
from types import SimpleNamespace
import pytest
from services.molcy import cierre,renderer,disk
from core.i18n import set_request_locale,reset_request_locale
from tests.molcy_ayudas import acta_con_cierre,escribir_mp4

@pytest.mark.parametrize("requested,expected",[("es","es"),("en","en"),("de","es")])
def test_idioma_capturado_antes_del_hilo(monkeypatch,tmp_path,requested,expected):
    submitted=[]
    monkeypatch.setattr(renderer,"_pool",SimpleNamespace(submit=lambda *args: submitted.append(args)))
    monkeypatch.setattr(renderer,"_reserved",set());monkeypatch.setattr(renderer,"_futures",{});monkeypatch.setattr(renderer,"_cancel_events",{})
    token=set_request_locale(requested)
    try: renderer.iniciar(tmp_path,job_id=str(uuid.uuid4()),pdb_id="TEST",sujeto="receptor_solo",formato="previsualizacion",dispositivo="gpu",capacidad={},fuente={})
    finally: reset_request_locale(token)
    state=json.loads((tmp_path/"estado.json").read_text(encoding="utf-8"))
    assert state["idioma"] == expected
    assert state["gpu_memoria"] == "automatica"
    assert "gpu_presupuesto" not in state
    assert submitted[0][2]["idioma"] == expected

@pytest.mark.parametrize("language",["es","en"])
def test_hilo_pasa_idioma_del_estado_y_valida_acta(monkeypatch,tmp_path,language):
    from tests.molcy_ayudas import gpu_simulada
    gpu_simulada(monkeypatch)
    monkeypatch.setattr(disk,"assert_budget",lambda *_:{})
    state={"id":str(uuid.uuid4()),"estado":"en_cola","formato":"previsualizacion","dispositivo":"gpu","sujeto":"receptor_solo","idioma":language,"fuente":{},"renderizador":{"motor":str(tmp_path),"blender":str(tmp_path/"blender.exe")}}
    def run(cmd,*,env,**kwargs):
        assert env["MOLCY_IDIOMA"] == language
        output=tmp_path/"salida";suffix=state["id"].replace("-","")[:12]
        output.mkdir(exist_ok=True)
        video=escribir_mp4(output/f"TEST_sitio_activo_previsualizacion_{suffix}.mp4",6.6)
        acta=acta_con_cierre();acta["cierre"].update(idioma=language,lema="REPRODUCIBLE STRUCTURAL EVIDENCE" if language=="en" else "EVIDENCIA ESTRUCTURAL REPRODUCIBLE")
        acta["render_ajustes"]={"motor":"BLENDER_EEVEE"}
        acta["video"]["sha256"]=renderer.sha256_archivo(video)
        (output/f"build_previsualizacion_{suffix}.json").write_text(json.dumps(acta),encoding="utf-8")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(renderer,"python_auxiliar",lambda:tmp_path/"python_auxiliar"/"python.exe")  # sin copiar el Python real (python_auxiliar.py)
    monkeypatch.setattr(renderer,"run_owned",run)
    renderer._ejecutar(tmp_path,state,"TEST")
    assert state["estado"] == "completo",state.get("motivo")

@pytest.mark.parametrize("change",[{"idioma":"en","lema":"EVIDENCIA ESTRUCTURAL REPRODUCIBLE"},{"idioma":"es"},{"idioma":"en","lema":""},{"idioma":"en","lema":"   "},{"idioma":None}])
def test_acta_de_otro_idioma_o_lema_ausente_se_rechaza(tmp_path,change):
    acta=acta_con_cierre();acta["cierre"].update(change)
    with pytest.raises(RuntimeError,match="idioma"):
        cierre.verificar(acta,escribir_mp4(tmp_path/"v.mp4",6.6),idioma="en")

@pytest.mark.parametrize("fmt",list(disk.FORMATS))
def test_presupuesto_reserva_dos_cierres_de_idioma(fmt):
    w,h,frames=disk.FORMATS[fmt];per=w*h*4+h+65536
    assert disk.required_bytes(fmt) == per*(frames*2+disk.BRAND_FRAMES[fmt]*2)+disk.ENCODE_BYTES+disk.RESERVE_BYTES
