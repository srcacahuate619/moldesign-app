import {beforeAll,describe,it,expect,vi} from "vitest";
import {render,screen,fireEvent,within} from "@testing-library/react";
import {EvaluationEvidencePanel} from "../EvaluationEvidencePanel";
import {ResultReadingPresentation} from "../ResultReadingPresentation";
import {RunDataExplorer,runDataFields} from "../RunDataExplorer";
import {ProParametersTab} from "../ProParametersTab";
import real from "../../../../app/laboratorio/evaluacion/lectura-qa.json";
import type {EvaluationResult} from "@/lib/types";
const result=real as unknown as EvaluationResult;
beforeAll(()=>{
  vi.stubGlobal("IntersectionObserver",class {
    observe(){} unobserve(){} disconnect(){} takeRecords(){return [];}
  });
});
describe("Experiencia experimental de resultados",()=>{
  it("mantiene una sola síntesis y títulos únicos al abrir el protocolo",()=>{
    const {container}=render(<ResultReadingPresentation><EvaluationEvidencePanel result={result} target={null} compact/><EvaluationEvidencePanel result={result} target={null} provenanceOnly/></ResultReadingPresentation>);
    const ids=[...container.querySelectorAll("[id]")].map(e=>e.id);expect(new Set(ids).size).toBe(ids.length);
    expect(screen.getByRole("heading",{name:"Qué obtuviste"})).toBeVisible();
    expect(screen.getByRole("heading",{name:"Protocolo y archivos de la corrida"})).toBeVisible();
    expect(screen.queryByRole("heading",{name:"Resumen de la evaluación"})).not.toBeInTheDocument();
    expect(container.querySelector("[data-run-provenance]")).toHaveTextContent("e9e2a024c4432a9f");
  });
  it("busca por nombre y filtra sin perder cero, falso, nulo, ausencias ni datos nuevos",()=>{
    const data={task_id:"qa",molecular_weight:0,lipinski_pass:false,log_p:null,new_producer_field:{nested:[false,0,null]}};
    const rows=runDataFields(data);
    expect(rows.find(row=>row.key==="molecular_weight")).toMatchObject({state:"recorded",value:0});
    expect(rows.find(row=>row.key==="lipinski_pass")).toMatchObject({state:"recorded",value:false});
    expect(rows.find(row=>row.key==="log_p")).toMatchObject({state:"null",value:null});
    expect(rows.find(row=>row.key==="hbd")).toMatchObject({state:"absent"});
    const {container}=render(<RunDataExplorer result={data}/>);
    fireEvent.change(screen.getByRole("searchbox"),{target:{value:"peso molecular"}});
    expect(container.querySelector('[data-field-key="molecular_weight"]')).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("1 de 111 campos");
    fireEvent.click(screen.getByRole("button",{name:"Limpiar filtros"}));
    fireEvent.change(screen.getByLabelText("Estado del dato"),{target:{value:"null"}});
    expect(container.querySelector('[data-field-key="log_p"]')).toBeInTheDocument();
    expect(container.querySelector('[data-field-key="molecular_weight"]')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:"Limpiar filtros"}));
    fireEvent.change(screen.getByLabelText("Área de los datos"),{target:{value:"other"}});
    expect(container.querySelector('[data-field-key="new_producer_field"]')).toHaveTextContent("new_producer_field");
    expect(screen.getByRole("status")).toHaveTextContent("1 de 111 campos");
  });
  it("conserva avisos de distintos productores aunque compartan su mensaje",()=>{
    const data={...result,scientific_warnings:[{codigo:"PRODUCTOR_A",severidad:"precaucion",mensaje:"Texto compartido"},{codigo:"PRODUCTOR_B",severidad:"critica",mensaje:"Texto compartido"}]} as unknown as EvaluationResult;
    const {container}=render(<ResultReadingPresentation><EvaluationEvidencePanel result={data} target={null} compact/></ResultReadingPresentation>);
    expect(container).toHaveTextContent("PRODUCTOR_A");expect(container).toHaveTextContent("PRODUCTOR_B");
    expect([...container.querySelectorAll('[data-critical="true"]')].some(node=>node.textContent?.includes("PRODUCTOR_B"))).toBe(true);
  });
  it("presenta ADMET parcial sin convertir los nulos en negativos y usa el estado propio de TabPFN",()=>{
    const data={...result,blood_viability_score:0,blood_hia_permeable:false,blood_bbb_permeable:null,blood_tabpfn_estado:"evaluado",blood_systemic_reactivity:[]};
    render(<ResultReadingPresentation><ProParametersTab result={data}/></ResultReadingPresentation>);
    const admet=screen.getByText("Predicciones ADMET · experimental").closest("details")!;
    expect(admet.open).toBe(false);
    fireEvent.click(admet.querySelector("summary")!);
    expect(admet.open).toBe(true);
    expect(admet).toHaveTextContent("0 / 100");
    expect(admet).toHaveTextContent("Resultados parciales");
    expect(within(admet).getAllByText("No registrado").length).toBeGreaterThan(0);
    expect(admet).not.toHaveTextContent("No hay predicciones ADMET guardadas");
    expect(admet).not.toHaveTextContent("No se evaluó la toxicidad");
  });
});
