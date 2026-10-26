import {describe,it,expect,vi,beforeEach} from "vitest";
import {render,screen,fireEvent,waitFor} from "@testing-library/react";
import {getContactMap} from "@/lib/api";
import type {InteractionsReport} from "@/lib/types";
import {ContactMapPanel,contactMapMatches} from "../ContactMapPanel";
import {ProXaiTab} from "../ProXaiTab";
import {ResultReadingPresentation} from "../ResultReadingPresentation";

vi.mock("@/lib/api",()=>({getContactMap:vi.fn(),getGnnAttentionSvg:vi.fn()}));
const api=vi.mocked(getContactMap);
const hash="a".repeat(64);
function report(task="run-a",rank=1):InteractionsReport {
  return {molecule_id:"mol-a",task_id:task,target_pdb_id:"TEST",pose_rank:rank,
    pose_source_path:"runs/poses.sdf",pose_source_sha256:hash,protein_source_path:"runs/receptor.pdbqt",protein_source_sha256:hash,protein_filter:"ATOM_only",engine:"distancias_sin_quimica",hydrogen_model:null,
    total_interactions:1,summary:{polar_contact:1},interactions_by_type:{},pharmacophore_features:{},analysis_ligand_sha256:hash,
    interactions:[{type:"polar_contact",residue:"SER1A",residue_name:"SER",residue_number:1,residue_chain:"A",distance:2.9,angle:null,strength:null,ligand_atom_indices:[0],protein_atom:"OG",ligand_coords:{x:0,y:0,z:0},protein_coords:{x:2.9,y:0,z:0},geometry:{distance:2.9}}],
    contact_map:{status:"ready",analysis_ligand_sha256:hash,svg:'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"></svg>',width:100,height:100,renderer:"rdkit:test",atoms:[{index:0,element:"O",x:20,y:20},{index:1,element:"O",x:80,y:80}],contacts:[{contact_index:0,atom_indices:[0],hidden_hydrogen_indices:[],reason:null}],highlighted_atom_indices:[0]},
  };
}
const view=(task="run-a")=><ResultReadingPresentation><ContactMapPanel moleculeId="mol-a" taskId={task} poses={[{rank:1},{rank:2}]}/></ResultReadingPresentation>;
beforeEach(()=>api.mockReset());

describe("Mapa de contactos ligado a la pose",()=>{
  it("localiza sólo los átomos del contacto seleccionado y conserva cero en sus coordenadas",async()=>{
    api.mockResolvedValue(report());const {container}=render(view());
    await screen.findByRole("img");const row=screen.getByRole("button",{name:/A:SER1/});
    expect(container.querySelectorAll('[data-selected-contact-atom]')).toHaveLength(0);
    fireEvent.click(row);expect(container.querySelector('[data-selected-contact-atom="0"]')).toBeInTheDocument();
    expect(container.querySelector('[data-selected-contact-atom="1"]')).not.toBeInTheDocument();
    expect(screen.getByText(/no confirma un puente de hidrógeno/)).toBeVisible();
    expect(screen.getByRole("heading",{name:/Contacto polar por distancia/})).toBeVisible();
    fireEvent.click(row);expect(container.querySelectorAll('[data-selected-contact-atom]')).toHaveLength(0);
    fireEvent.change(screen.getByLabelText("Pose del mapa"),{target:{value:"2"}});
    await waitFor(()=>expect(api).toHaveBeenLastCalledWith("mol-a","run-a",2,expect.any(AbortSignal)));
  });
  it("descarta la respuesta tardía de otra corrida aunque el transporte ignore la cancelación",async()=>{
    let resolveOld!:(value:InteractionsReport)=>void;
    api.mockImplementationOnce(()=>new Promise(resolve=>{resolveOld=resolve;})).mockResolvedValue(report("run-b"));
    const {rerender,container}=render(view());rerender(view("run-b"));await screen.findByRole("img");
    resolveOld(report("run-a"));await waitFor(()=>expect(container.querySelector('[data-contact-task="run-b"]')).toBeInTheDocument());
    expect(container.querySelector('[data-contact-task="run-a"]')).not.toBeInTheDocument();
  });
  it("una respuesta discordante no pinta nada y permite reintentar",async()=>{
    api.mockResolvedValue(report("other"));render(view());
    expect(await screen.findByText(/La respuesta no coincide/)).toBeVisible();expect(screen.queryByRole("img")).not.toBeInTheDocument();
    api.mockResolvedValue(report());fireEvent.click(screen.getByRole("button",{name:"Reintentar lectura"}));await screen.findByRole("img");
  });
  it("conserva contactos sin diagrama sin inventar una localización",async()=>{
    const data=report();data.contact_map={status:"unavailable",reason:"UNBOUND_ATOM_INDICES",analysis_ligand_sha256:hash};
    api.mockResolvedValue(data);render(view());await screen.findByRole("button",{name:/A:SER1/});
    expect(screen.queryByRole("img")).not.toBeInTheDocument();fireEvent.click(screen.getByRole("button",{name:/A:SER1/}));
    expect(screen.getByText(/no se puede localizar con garantía/)).toBeVisible();
  });
  it("sin corrida no consulta la última evaluación de la molécula",()=>{
    render(<ContactMapPanel moleculeId="mol-a"/>);expect(api).not.toHaveBeenCalled();expect(screen.getByText(/corrida guardada e identificable/)).toBeVisible();
  });
  it("el mapa funciona sin SHAP y no reactiva un SVG GNN heredado",async()=>{
    api.mockResolvedValue(report());const {container}=render(<ResultReadingPresentation><ProXaiTab shapValues={null} gnnAttention={[1]} gnnAttentionSvg='<svg id="legacy-heuristic"/>' gnnPharmacophores={{fake:100}} moleculeId="mol-a" taskId="run-a" poses={[{rank:1}]}/></ResultReadingPresentation>);
    await screen.findByRole("img");expect(container.querySelector('#legacy-heuristic')).not.toBeInTheDocument();
  });
  it("rechaza índices incompatibles y no confunde el hash de archivo con el del SDF analizado",()=>{
    const data=report();expect(contactMapMatches(data,"mol-a","run-a",1)).toBe(true);
    data.contact_map!.contacts![0].atom_indices=[1];expect(contactMapMatches(data,"mol-a","run-a",1)).toBe(false);
    data.contact_map!.contacts![0].atom_indices=[0];data.analysis_ligand_sha256="b".repeat(64);
    expect(contactMapMatches(data,"mol-a","run-a",1)).toBe(false);
  });
  it("conserva un ángulo cero declarado y permite ampliar sin cambiar de pose",async()=>{
    const data=report();data.interactions[0].geometry={DHA_angle:0};api.mockResolvedValue(data);
    render(view());await screen.findByRole("img");fireEvent.click(screen.getByRole("button",{name:/A:SER1/}));
    expect(screen.getByText("0.0°")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:"Ampliar dibujo"}));expect(screen.getByLabelText("Ampliación del dibujo")).toHaveTextContent("150%");
    expect(api).toHaveBeenCalledTimes(1);
  });
});
