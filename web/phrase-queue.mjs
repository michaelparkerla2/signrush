// Only the worker can determine availability across identities, approvals and caps.
export function presentQueue(dashboard){
 const data=dashboard||{};
 const trusted=data.catalogBatch==='daily-use-v1'&&data.catalogSize===200&&Number.isInteger(data.signAvailable)&&data.signAvailable>=0;
 return {reviewAvailable:0,pending:0,approved:0,submitted:0,...data,
  signAvailable:trusted?data.signAvailable:null,signInProgress:Boolean(data.signInProgress),queueKnown:trusted};
}
