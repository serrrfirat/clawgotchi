export const config = {
  runtime: 'edge',
};

export default async function handler(request) {
  try {
    const { prompt } = await request.json();
    
    if (!prompt) {
      return Response.json({ error: 'No prompt provided' }, { status: 400 });
    }
    
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      return Response.json({ error: 'GEMINI_API_KEY not configured' }, { status: 500 });
    }
    
    const response = await fetch(
      'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-goog-api-key': apiKey,
        },
        body: JSON.stringify({
          contents: [{
            parts: [{
              text: `Generate ASCII art for: ${prompt}

Rules:
- Use only ASCII characters
- Keep it under 80 columns wide
- Make it visually clear and recognizable
- No markdown code blocks, just the raw ASCII
- Be creative with the design`
            }]
          }]
        })
      }
    );
    
    const data = await response.json();
    
    if (data.error) {
      return Response.json({ error: data.error.message }, { status: 500 });
    }
    
    const result = data.candidates?.[0]?.content?.parts?.[0]?.text || 'No result';
    
    return Response.json({ result });
  } catch (err) {
    return Response.json({ error: err.message }, { status: 500 });
  }
}
