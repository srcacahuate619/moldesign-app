const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const AUD=path.resolve(__dirname,'..');
const pointer=JSON.parse(fs.readFileSync(path.join(AUD,'evidencia/archivo-fase-a.json'),'utf8'));
const archive=path.resolve(process.env.MOLDESIGN_I18N_EVIDENCE_ROOT||pointer.raiz_archivo);
const manifestPath=path.join(archive,'MANIFIESTO_SHA256.json');
const digest=buffer=>crypto.createHash('sha256').update(buffer).digest('hex');
const bytes=fs.readFileSync(manifestPath);
if(digest(bytes)!==pointer.manifiesto_sha256)throw new Error('El manifiesto externo no coincide con su SHA-256');
const manifest=JSON.parse(bytes);
function archivo(relative){
  if(path.isAbsolute(relative))return relative;
  const local=path.resolve(AUD,relative);
  if(!local.startsWith(AUD+path.sep))throw new Error('Ruta fuera de la auditoría');
  if(fs.existsSync(local))return local;
  const external=path.resolve(archive,'repo/docs/auditorias/i18n-frontend-2026-10-25',relative);
  if(!external.startsWith(archive+path.sep))throw new Error('Ruta fuera del archivo');
  if(!fs.existsSync(external))throw new Error('Evidencia no encontrada: '+relative);
  return external;
}
function verificar(){
  for(const row of manifest.archivos){const file=path.resolve(archive,row.ruta_archivo);if(!file.startsWith(archive+path.sep))throw new Error('Ruta de manifiesto fuera del archivo');const data=fs.readFileSync(file);if(data.length!==row.bytes||digest(data)!==row.sha256)throw new Error('Evidencia alterada: '+row.ruta_repo);}
  return {archivos_verificados:manifest.archivos.length,manifiesto_sha256:pointer.manifiesto_sha256};
}
if(require.main===module)console.log(JSON.stringify(verificar()));
module.exports={archivo,verificar,pointer};
