import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { EngineStatusBar } from "../EngineStatusBar";
import { Ayuda } from "../ui/Ayuda";
import { ExternalLink } from "../ui/ExternalLink";
import { LocalDocViewer } from "../ui/LocalDocViewer";
import { mockFetch } from "../../vitest.setup";
const model=vi.hoisted(()=>({locale:"es" as "es"|"en",engine:{state:"starting",port:null,detail:null},open:vi.fn()}));
vi.mock("../../context/LanguageContext",async importOriginal=>{const actual=await importOriginal<typeof import("../../context/LanguageContext")>();const t=(key:string,values?:Readonly<Record<string,string|number>>)=>actual.interpolar(actual.TRANSLATIONS[model.locale][key]??key,values);return{...actual,useLanguage:()=>({locale:model.locale,t})};});
vi.mock("../../hooks/useDownload",()=>({useDownload:()=>({engine:model.engine,retryEngine:vi.fn()})}));
vi.mock("../../lib/openExternal",()=>({esExterno:()=>true,openExternal:(url:string)=>model.open(url)}));
afterEach(cleanup);
describe.each(["es","en"] as const)("superficies en %s",locale=>{
  // (Fase 6.6) El test de ProviderBadge murio con el panel interno.
 it("traduce el estado inicial y la explicación del motor",()=>{
   model.locale=locale;model.engine={state:"starting",port:null,detail:null};
   const {rerender}=render(<EngineStatusBar/>);
   expect(screen.getByRole("status")).toHaveTextContent(locale==="es"?"Iniciando motor…":"Starting engine…");
   model.engine={state:"not_installed",port:null,detail:null};rerender(<EngineStatusBar/>);
   expect(screen.getByRole("status")).toHaveTextContent(locale==="es"?"Falta una parte del runtime":"Part of the compute runtime is missing");
 });
 it("traduce el atributo accesible de ayuda",()=>{
   model.locale=locale;render(<Ayuda titulo="Preflight check">Help</Ayuda>);
   const button=screen.getByRole("button",{name:locale==="es"?"Qué significa: Preflight check":"What it means: Preflight check"});
   fireEvent.click(button);expect(screen.getByRole("dialog")).toBeInTheDocument();
 });
 it("traduce el fallo al abrir un enlace sin enviar nada",async()=>{
   model.locale=locale;model.open.mockRejectedValueOnce(new Error("open failed"));
   render(<ExternalLink href="https://example.test/" onError={vi.fn()}>Open</ExternalLink>);fireEvent.click(screen.getByRole("link"));
   expect(await screen.findByRole("alert")).toHaveTextContent(locale==="es"?"No se pudo abrir el enlace":"The link could not be opened");
 });
 it("traduce el fallo del visor local conservando ruta y causa",async()=>{
   model.locale=locale;mockFetch.mockRejectedValueOnce(new Error("missing asset"));
   render(<LocalDocViewer doc={{path:"/legal/missing.md",title:"Document"}} onClose={vi.fn()}/>);
   expect(await screen.findByText(locale==="es"?/No se pudo cargar \/legal\/missing.md/:/Could not load \/legal\/missing.md/)).toBeInTheDocument();
 });
});
