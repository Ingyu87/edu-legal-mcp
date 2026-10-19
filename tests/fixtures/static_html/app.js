
const name = document.querySelector('[name=studentName]').value;
localStorage.setItem('draft', document.querySelector('#writing').value);
fetch('https://api.openai.com/v1/chat/completions', {
  method:'POST', headers:{'Content-Type':'application/json'},
  body: JSON.stringify({model:'gpt-4o-mini', messages:[{role:'user', content: document.querySelector('#writing').value}]})
});
