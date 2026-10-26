// Instrumentación de QA de webpack: no cambia el código emitido ni el next.config.
const fs = require('node:fs');
const path = require('node:path');
if (process.env.QA_BUNDLE_ROOT) {
  const config = require(path.join(process.env.QA_BUNDLE_ROOT,'next.config.js'));
  const original = config.webpack;
  config.webpack = (c, options) => {
    c = original(c, options);
    if (!options.isServer) c.plugins.push({apply(compiler) {
      compiler.hooks.done.tap('QaDependencyEvidence', stats => {
        const list=[];
        function visit(m, files) {
          list.push({name:m.resource || m.identifier?.(),chunks:files});
          for (const inner of m.modules || []) visit(inner.module || inner,files);
        }
        for (const chunk of stats.compilation.chunks) {
          for (const m of stats.compilation.chunkGraph.getChunkModulesIterable(chunk)) visit(m,[...chunk.files]);
        }
        fs.writeFileSync(path.join(process.env.QA_BUNDLE_ROOT,'bundle-modules.json'),JSON.stringify(list,null,2));
      });
    }});
    return c;
  };
}
