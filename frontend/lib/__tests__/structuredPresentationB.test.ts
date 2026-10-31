import { describe, expect, it } from "vitest";
import { newlyLoadedStructureRef, structureByRef } from "../molstarStructureIdentity";
import { saveFailureKind } from "../evaluationErrorPresentation";
import { ApiError } from "../api";
describe.each(["es","en"])("identidad estructurada en %s",locale=>{
 it("enfoca el candidato por referencia aunque cambien los nombres o se añada atención GNN después",()=>{
   const receptor={cell:{transform:{ref:"protein"}},label:locale==="es"?"Receptor":"Receptor"};
   const candidate={cell:{transform:{ref:"pose"}},label:locale==="es"?"Mi Diseño MolDesign (Candidato)":"My MolDesign Design (Candidate)"};
   const attention={cell:{transform:{ref:"attention"}},label:locale==="es"?"Atención GNN 3D":"3D GNN Attention"};
   const ref=newlyLoadedStructureRef(["protein"],[receptor,candidate]);
   expect(ref).toBe("pose");expect(structureByRef([receptor,candidate,attention],ref)).toBe(candidate);
   expect(newlyLoadedStructureRef(["protein"],[receptor,candidate,attention])).toBeNull();
   expect(structureByRef([receptor,attention],ref)).toBeUndefined();
 });
 it("clasifica HTTP por estado sin reconocer ni números ni prosa del mensaje",()=>{
   const message=locale==="es"?"No autenticado, molécula no encontrada":"Unrelated English text";
   expect(saveFailureKind(new ApiError(401,message))).toBe("session");
   expect(saveFailureKind(new ApiError(403,message))).toBe("session");
   expect(saveFailureKind(new ApiError(404,message))).toBe("missing");
   expect(saveFailureKind(new ApiError(500,message))).toBe("other");
   expect(saveFailureKind(new Error("401 403 404 No autenticado token no encontrada"))).toBe("other");
 });
});
