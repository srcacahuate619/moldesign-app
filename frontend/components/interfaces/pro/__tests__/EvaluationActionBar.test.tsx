import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { KeepAliveContext } from "@/context/KeepAliveContext";
import { EvaluationActionBar, EVALUATION_ACTIONS_OUTLET } from "../EvaluationActionBar";
import { EvaluationEvidencePanel } from "../EvaluationEvidencePanel";
import { ResultReadingPresentation } from "../ResultReadingPresentation";
import type { EvaluationResult } from "@/lib/types";
import real from "../../../../app/laboratorio/evaluacion/lectura-qa.json";

afterEach(() => { document.getElementById(EVALUATION_ACTIONS_OUTLET)?.remove(); });

describe("Acciones persistentes de la corrida", () => {
  it("envía cada acción al manejador vigente y conserva el estado Guardado", () => {
    const report=vi.fn(), preview=vi.fn(), complex=vi.fn(), save=vi.fn(), next=vi.fn(), integrity=vi.fn();
    const integrityAction={onClick:integrity,disabled:false,label:"Registrar integridad en Solana",title:"Abre el diálogo",state:"sin-sello"};
    const {rerender}=render(<EvaluationActionBar onDownloadReport={report} onViewReport={preview} onDownloadComplex={complex} onSave={save} integrityAction={integrityAction}/>);
    const bar=screen.getByRole("navigation",{name:"Acciones del resultado"});
    expect(bar.querySelectorAll("button")).toHaveLength(5);
    for(const name of ["Descargar informe de evaluación","Ver informe de evaluación","Complejo .PDB","Guardar en MolDex","Registrar integridad en Solana"]){
      fireEvent.click(screen.getByRole("button",{name}));
    }
    for(const action of [report,preview,complex,save,integrity])expect(action).toHaveBeenCalledTimes(1);
    rerender(<EvaluationActionBar onDownloadReport={next} onViewReport={preview} onDownloadComplex={complex} onSave={save} isSaved integrityAction={integrityAction}/>);
    fireEvent.click(screen.getByRole("button",{name:"Descargar informe de evaluación"}));
    expect(next).toHaveBeenCalledTimes(1);expect(report).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button",{name:/Guardad/})).toBeVisible();
  });

  it.each([['vigente','Certificado'],['corrida-anterior','Sello desfasado'],['indeterminado','Sello sin corrida registrada']])("conserva la restricción y la explicación del sello %s",(state,label)=>{
    const action=vi.fn();
    render(<EvaluationActionBar onSave={vi.fn()} integrityAction={{onClick:action,disabled:true,label,title:"Motivo original de la corrida",state}}/>);
    const button=screen.getByRole("button",{name:label});
    expect(button).toBeDisabled();expect(button).toHaveAttribute("title","Motivo original de la corrida");
    fireEvent.click(button);expect(action).not.toHaveBeenCalled();
    expect(screen.getByRole("button",{name:"Guardar en MolDex"})).toBeEnabled();
  });

  it("retira la barra al ocultar la pestaña y la recupera al volver", () => {
    const view=(active:boolean)=><KeepAliveContext.Provider value={active}><EvaluationActionBar onSave={vi.fn()}/></KeepAliveContext.Provider>;
    const {rerender}=render(view(true));
    expect(screen.getByRole("navigation",{name:"Acciones del resultado"})).toBeInTheDocument();
    rerender(view(false));expect(screen.queryByRole("navigation",{name:"Acciones del resultado"})).not.toBeInTheDocument();
    rerender(view(true));expect(screen.getByRole("navigation",{name:"Acciones del resultado"})).toBeInTheDocument();
  });

  it("usa el espacio reservado del workspace y no deja el portal después de desmontar", () => {
    const outlet=document.createElement("div");outlet.id=EVALUATION_ACTIONS_OUTLET;
    vi.spyOn(outlet,"getClientRects").mockReturnValue([{}] as unknown as DOMRectList);document.body.append(outlet);
    const {unmount}=render(<EvaluationActionBar onSave={vi.fn()}/>);
    expect(outlet.contains(screen.getByRole("navigation",{name:"Acciones del resultado"}))).toBe(true);
    unmount();expect(outlet.children).toHaveLength(0);
  });

  it("no ofrece acciones falsas en una muestra de lectura sin conexión", () => {
    render(<EvaluationActionBar unavailableReason="Muestra sin caso"/>);
    const buttons=screen.getAllByRole("button");expect(buttons).toHaveLength(5);
    for(const button of buttons){expect(button).toBeDisabled();expect(button).toHaveAttribute("title","Muestra sin caso");}
  });
});

describe("Identidad visible", () => {
  it("muestra el identificador real como texto y lo actualiza con la corrida", () => {
    const first={...real,task_id:"51c1f48e-c8f0-4c3a-a0d8-4fc7cef79724"} as unknown as EvaluationResult;
    const view=(result:EvaluationResult)=><ResultReadingPresentation><EvaluationEvidencePanel result={result} target={null} compact/></ResultReadingPresentation>;
    const {rerender}=render(view(first));
    const identity=screen.getByText(first.task_id!,{exact:true}).closest("p")!;
    expect(identity).toHaveTextContent(`Identidad de la corrida: ${first.task_id}`);expect(identity).toBeVisible();expect(identity.closest("details")).toBeNull();
    rerender(view({...first,task_id:"another-run"}));
    expect(screen.queryByText(first.task_id!,{exact:true})).not.toBeInTheDocument();expect(screen.getByText("another-run",{exact:true})).toBeVisible();
  });
});
