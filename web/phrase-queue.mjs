import {DAILY_BATCH,DAILY_PHRASES,MAX_TASKS,TARGET_SIGNERS} from './daily-phrases.mjs';

export function coverageCounts(doc){
 const counts={};
 if(!doc||typeof doc!=='object')return counts;
 for(const [key,value] of Object.entries(doc))if(key.startsWith('DAILY-')&&Number.isInteger(value))counts[key]=value;
 return counts;
}
export function choosePhrase(phrases,exposed,coverage={},pick=Math.random){
 const options=phrases.filter(phrase=>!exposed.has(phrase.id)&&(coverage[phrase.id]||0)<TARGET_SIGNERS);
 if(!options.length)return null;
 const lowest=Math.min(...options.map(phrase=>coverage[phrase.id]||0));
 const tied=options.filter(phrase=>(coverage[phrase.id]||0)===lowest);
 return tied[Math.min(tied.length-1,Math.floor(pick()*tied.length))];
}
export function availableCount(phrases,exposed,coverage={},reserved=0){
 const open=phrases.filter(phrase=>!exposed.has(phrase.id)&&(coverage[phrase.id]||0)<TARGET_SIGNERS).length;
 const slots=Math.max(0,MAX_TASKS-(Number.isInteger(reserved)?reserved:0));
 return Math.min(slots,open);
}
// A dashboard written before the daily catalog has no batch marker. Those zeros are stale.
export function presentQueue(dashboard){
 const data=dashboard||{};
 const trusted=data.catalogBatch===DAILY_BATCH&&Number.isInteger(data.signAvailable);
 const signInProgress=Boolean(data.signInProgress);
 const base=trusted?data.signAvailable:DAILY_PHRASES.length;
 return {reviewAvailable:0,pending:0,approved:0,submitted:0,...data,signAvailable:signInProgress?Math.max(base,1):base,signInProgress};
}
