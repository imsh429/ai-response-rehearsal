export async function api(path, options={}) {
  const r=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json',...options.headers}})
  if(!r.ok){let message;try{const data=await r.json();message=typeof data.detail==='string'?data.detail:'입력 내용을 확인해 주세요.'}catch{message=`서버 요청 실패 (${r.status})`}throw new Error(message)}
  return r.json()
}
export const post=(path,body={})=>api(path,{method:'POST',body:JSON.stringify(body)})

// Handles UTF-8 boundaries, multiple events per chunk, and split SSE frames.
export async function streamMessage(id,content,onToken,signal){
  const r=await fetch(`/api/sessions/${id}/messages`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content}),signal})
  if(!r.ok){const data=await r.json();throw new Error(typeof data.detail==='string'?data.detail:'메시지 전송 실패')}
  const reader=r.body.getReader(),decoder=new TextDecoder()
  let buffer='',doneEvent=null
  const consume=()=>{
    let split
    while((split=buffer.indexOf('\n\n'))!==-1){
      const frame=buffer.slice(0,split);buffer=buffer.slice(split+2)
      let event='message';const lines=[]
      for(const line of frame.split('\n')){if(line.startsWith('event:'))event=line.slice(6).trim();if(line.startsWith('data:'))lines.push(line.slice(5).trimStart())}
      if(!lines.length)continue
      const data=JSON.parse(lines.join('\n'))
      if(event==='token')onToken(data)
      if(event==='error')throw new Error(data.message)
      if(event==='done')doneEvent=data
    }
  }
  try{
    while(true){const {done,value}=await reader.read();if(done){buffer+=decoder.decode();consume();break}buffer+=decoder.decode(value,{stream:true});consume()}
    if(!doneEvent)throw new Error('연결이 중단됐습니다. 저장된 대화를 확인한 뒤 다시 시도하세요.')
    return doneEvent
  }finally{await reader.cancel().catch(()=>{});reader.releaseLock()}
}
