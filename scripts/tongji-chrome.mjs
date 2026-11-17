// Artifact Tool helper; call on a blank 1280 x 720 slide, or after removing old chrome.
// Import the reference deck when possible. This helper only adds the common frame.
export function addTongjiChrome(slide,{title,subject,section,pageNumber,logoBytes}) {
 if(![title,subject,section].every(v=>typeof v==='string'&&v.trim()))throw new Error('title, subject and section are required');
 if(!Number.isInteger(pageNumber)||pageNumber<1)throw new Error('pageNumber must be a positive integer');
 if(!logoBytes?.length)throw new Error('Load assets/tongji-logo.png as logoBytes');
 function label(name,value,x,y,w,h,size,font,bold=false,alignment='left'){
  const s=slide.shapes.add({geometry:'textbox',name,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
  s.text=value;s.text.style={fontSize:size,typeface:font,color:'#000000',bold,alignment,insets:0,autoFit:'none',wrap:'none',verticalAlignment:'middle'};
  return s;
 }
 function polygon(name,x,w,points){return slide.shapes.add({geometry:'custom',name,position:{left:x,top:660,width:w,height:60},fill:'#E7E7E7',line:{fill:'none',width:0},customPaths:[{width:w,height:60,commands:[{moveTo:points[0]},...points.slice(1).map(q=>({lineTo:q})),{close:{}}]}]});}
 slide.background.fill='#FFFFFF';
 label('完整页标题',title,64,22,1152,46,31,'Songti SC',true);
 slide.shapes.add({geometry:'rect',name:'黑色标题分割线',position:{left:40,top:76,width:1200,height:1},fill:'#000000',line:{fill:'none',width:0}});
 polygon('浅灰页脚主栏',0,1028,[{x:0,y:0},{x:1028,y:0},{x:1012,y:60},{x:0,y:60}]);
 polygon('浅灰校标栏',1030,250,[{x:16,y:0},{x:250,y:0},{x:250,y:60},{x:0,y:60}]);
 label('页脚论文短名',subject,28,672,250,38,25,'PingFang SC',true);
 label('页脚章节主题',section,310,672,500,38,25,'PingFang SC',false,'center');
 label('页脚页码',`Page ${pageNumber}`,865,672,140,38,25,'PingFang SC',false,'center');
 slide.images.add({blob:logoBytes,contentType:'image/png',alt:'同济大学官方校标与中英文校名',fit:'contain',position:{left:1066,top:669,width:190,height:46.04}});
}
