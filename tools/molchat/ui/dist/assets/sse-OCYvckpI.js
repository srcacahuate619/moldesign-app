function a(){let e="";return{push(r){e+=r;const s=[];let t=e.indexOf(`

`);for(;t>=0;){const c=e.slice(0,t);e=e.slice(t+2);const i=c.split(`
`).filter(n=>n.startsWith("data:")).map(n=>n.slice(5).trim());if(i.length>0)try{s.push(JSON.parse(i.join(`
`)))}catch{}t=e.indexOf(`

`)}return s}}}export{a as createSseParser};
