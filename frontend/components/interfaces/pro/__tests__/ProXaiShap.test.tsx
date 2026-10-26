import {beforeAll,describe,it,expect} from "vitest";
import {render,screen,fireEvent,waitFor,within} from "@testing-library/react";
import {ProXaiTab} from "../ProXaiTab";
import {ResultReadingPresentation} from "../ResultReadingPresentation";

beforeAll(()=>{
  Object.defineProperty(HTMLDialogElement.prototype,"showModal",{configurable:true,value:function(this:HTMLDialogElement){this.setAttribute("open","");}});
  Object.defineProperty(HTMLDialogElement.prototype,"close",{configurable:true,value:function(this:HTMLDialogElement){this.removeAttribute("open");this.dispatchEvent(new Event("close"));}});
});
const show=(values:Record<string,number>|null)=><ResultReadingPresentation><ProXaiTab shapValues={values} gnnAttention={null} gnnAttentionSvg={null} gnnPharmacophores={null}/></ResultReadingPresentation>;

describe("Gráfica SHAP recuperada",()=>{
  it("conserva orden, valores exactos y claves futuras, distinguiendo negativo, positivo y cero",()=>{
    const values={mw:-0.23179,qed:0.12511,new_producer_feature:0};
    const {container}=render(show(values));
    const rows=[...container.querySelectorAll<HTMLButtonElement>("[data-shap-feature]")];
    expect(rows.map(row=>row.dataset.shapFeature)).toEqual(Object.keys(values));
    expect(rows.map(row=>Number(row.dataset.shapValue))).toEqual(Object.values(values));
    expect(rows.map(row=>row.dataset.direction)).toEqual(["negative","positive","zero"]);
    expect(screen.getByText("-0.232")).toBeVisible();expect(screen.getByText("+0.125")).toBeVisible();expect(screen.getByText("0.000")).toBeVisible();
    expect(screen.getByRole("button",{name:/new producer feature: 0/})).toHaveAttribute("aria-haspopup","dialog");
    expect(container.querySelectorAll("[data-shap-chart] details")).toHaveLength(0);
  });
  it("abre el detalle con el valor íntegro y conserva el alcance del modelo",async()=>{
    render(show({vina_best_score:0.123456789}));
    const opener=screen.getByRole("button",{name:/0.123456789/});fireEvent.click(opener);
    const dialog=await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("+0.123456789");expect(dialog).toHaveTextContent("vina_best_score");
    expect(dialog).toHaveTextContent("salida del modelo");expect(dialog).not.toHaveTextContent("AUMENTA la afinidad predicha");
    fireEvent.click(within(dialog).getByRole("button",{name:"Cerrar"}));
    await waitFor(()=>expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
  it("mantiene explícita la ausencia de SHAP y el dominio sin determinar",()=>{
    const {container}=render(show(null));
    expect(container.querySelector("[data-shap-chart]")).not.toBeInTheDocument();
    expect(screen.getByText("No disponible",{exact:false})).toBeInTheDocument();
  });
});
