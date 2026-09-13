declare module "molstar/build/viewer/molstar.js" {
  export class Viewer {
    static create(element: HTMLElement, options?: any): Promise<Viewer>;
    loadStructureFromData(data: string, format: string, options?: any): Promise<void>;
    loadAllFormats(url: string): Promise<void>;
    dispose(): void;
    resize(width?: number, height?: number): void;
  }
}

declare module "molstar/build/viewer/molstar.css";
