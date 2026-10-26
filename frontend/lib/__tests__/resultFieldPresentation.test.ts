import {describe,it,expect} from "vitest";
import {RESULT_FIELD_KEYS} from "../resultFieldKeys";
import {RESULT_FIELD_PRESENTATION,resultFieldPresentation,resultFieldMatches} from "../resultFieldPresentation";
describe("Etiquetas editoriales del registro íntegro",()=>{
  it("clasifica y etiqueta el inventario completo sin descartar claves futuras",()=>{
    for(const key of RESULT_FIELD_KEYS){expect(RESULT_FIELD_PRESENTATION[key],key).toBeDefined();expect(resultFieldPresentation(key).es).toBeTruthy();expect(resultFieldPresentation(key).en).toBeTruthy();}
    expect(resultFieldPresentation("new_producer_field")).toEqual({group:"other",es:"new_producer_field",en:"new_producer_field"});
  });
  it("encuentra nombres en ambos idiomas, claves, alias y valores anidados",()=>{
    for(const query of ["peso molecular","molecular weight","molecular_weight","MW","masa molecular"]){expect(resultFieldMatches("molecular_weight",0,query),query).toBe(true);}
    expect(resultFieldMatches("ligand_state",{ph:7.4},"protonacion")).toBe(true);
    expect(resultFieldMatches("new_producer_field",{nested:[false,"needle"]},"needle")).toBe(true);
    expect(resultFieldMatches("molecular_weight",0,"inexistente")).toBe(false);
  });
});
