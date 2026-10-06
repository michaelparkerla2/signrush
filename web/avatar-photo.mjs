export const PHOTO_LIMIT=24000;
export const isAvatarPhoto=value=>typeof value==='string'&&value.length<=PHOTO_LIMIT&&/^data:image\/jpeg;base64,\/9j\/[A-Za-z0-9+/]+={0,2}$/.test(value);
export async function prepareAvatarPhoto(file){
 if(!file||!['image/jpeg','image/png','image/webp'].includes(file.type))throw Error('Choose a JPG, PNG or WebP photo.');
 if(file.size>8*1024*1024)throw Error('Choose a photo smaller than 8 MB.');
 let bitmap;
 try{bitmap=await createImageBitmap(file);}catch{throw Error('This photo could not be opened. Try another image.');}
 try{
  if(!bitmap.width||!bitmap.height||bitmap.width*bitmap.height>40000000)throw Error('Choose a photo under 40 megapixels.');
  const canvas=document.createElement('canvas');canvas.width=canvas.height=160;
  const ctx=canvas.getContext('2d');ctx.fillStyle='#fff';ctx.fillRect(0,0,160,160);
  const side=Math.min(bitmap.width,bitmap.height);ctx.drawImage(bitmap,(bitmap.width-side)/2,(bitmap.height-side)/2,side,side,0,0,160,160);
  for(const quality of [.85,.7,.5,.3]){const result=canvas.toDataURL('image/jpeg',quality);if(isAvatarPhoto(result))return result;}
  throw Error('This photo is too detailed. Try a simpler portrait.');
 }finally{bitmap.close();}
}
