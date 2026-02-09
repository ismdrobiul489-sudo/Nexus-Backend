from google.genai import Client
from openai import OpenAI
import os
import uuid

class ContentService:
    
    @staticmethod
    async def generate_with_gemini(api_key: str, prompt: str, model: str = 'gemini-2.0-flash') -> str:
        import httpx
        if not api_key:
            raise ValueError("Gemini API Key is missing")
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=headers, timeout=60.0)
                if response.status_code != 200:
                   raise Exception(f"Gemini API Error ({response.status_code}): {response.text}")
                   
                data = response.json()
                # Extract text
                return data.get("candidates", [])[0].get("content", {}).get("parts", [])[0].get("text", "Error")
            except Exception as e:
                print(f"Gemini Error: {e}")
                raise Exception(f"Gemini API Failed: {str(e)}")

    @staticmethod
    async def generate_with_openrouter(api_key: str, prompt: str, model: str = 'openrouter/auto', base_url: str = None) -> str:
        from openai import AsyncOpenAI
        if not api_key:
            raise ValueError("OpenRouter API Key is missing")
            
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or "https://openrouter.ai/api/v1",
        )
        
        try:
            response = await client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model,
            )
            return response.choices[0].message.content or "Error generating content."
        except Exception as e:
            print(f"OpenRouter Error: {e}")
            raise Exception(f"OpenRouter API Failed: {str(e)}")

    @staticmethod
    async def generate_with_groq(api_key: str, prompt: str, model: str = 'llama-3.3-70b-versatile', base_url: str = None) -> str:
        from openai import AsyncOpenAI
        if not api_key:
            raise ValueError("Groq API Key is missing")
            
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or "https://api.groq.com/openai/v1",
        )
        
        try:
            response = await client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model,
            )
            return response.choices[0].message.content or "Error generating content."
        except Exception as e:
            print(f"Groq Error: {e}")
            raise Exception(f"Groq API Failed: {str(e)}")
            
    @staticmethod
    async def validate_gemini_key(api_key: str) -> dict:
        """Validates key by fetching real models from Google API."""
        import httpx
        if not api_key:
            return {"isValid": False, "models": []}
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    # Filter for 'generateContent' supported models
                    models = [
                        m["name"].replace("models/", "") 
                        for m in data.get("models", []) 
                        if "generateContent" in m.get("supportedGenerationMethods", [])
                    ]
                    return {"isValid": True, "models": models}
                else:
                    return {"isValid": False, "models": [], "error": f"API Error: {response.status_code}"}
            except Exception as e:
                return {"isValid": False, "models": [], "error": str(e)}

    @staticmethod
    async def validate_openrouter_key(api_key: str) -> dict:
        """Validates key by fetching real models from OpenRouter with Free-First sorting."""
        import httpx
        if not api_key:
            return {"isValid": False, "models": []}
            
        url = "https://openrouter.ai/api/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    raw_models = data.get("data", [])
                    
                    def is_free(m):
                        # 1. Check ID for ':free' suffix
                        if m.get("id", "").lower().endswith(":free"):
                            return True
                        # 2. Check pricing metadata
                        pricing = m.get("pricing", {})
                        try:
                            prompt_price = float(pricing.get("prompt", 0))
                            comp_price = float(pricing.get("completion", 0))
                            return prompt_price == 0 and comp_price == 0
                        except:
                            return False

                    # Sort: Free models first, then alphabetically by ID
                    sorted_list = sorted(raw_models, key=lambda m: (not is_free(m), m.get("id")))
                    
                    models = [m["id"] for m in sorted_list]
                    return {"isValid": True, "models": models[:500]} # Increase limit to 500
                else:
                    return {"isValid": False, "models": [], "error": f"API Error: {response.status_code}"}
            except Exception as e:
                return {"isValid": False, "models": [], "error": str(e)}

    @staticmethod
    async def validate_groq_key(api_key: str) -> dict:
        """Validates key by fetching real models from Groq."""
        import httpx
        if not api_key:
            return {"isValid": False, "models": []}
            
        url = "https://api.groq.com/openai/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    models = [m["id"] for m in data.get("data", [])]
                    return {"isValid": True, "models": models}
                else:
                    return {"isValid": False, "models": [], "error": f"API Error: {response.status_code}"}
            except Exception as e:
                return {"isValid": False, "models": [], "error": str(e)}

    @staticmethod
    async def generate_image(provider: str, api_key: str, prompt: str, worker_url: str = None, model: str = None, width: int = 1024, height: int = 1024) -> bytes:
        import httpx
        
        provider_lower = provider.lower()
        
        if provider_lower == "cloudflare":
            # Cloudflare Worker Proxy - Strictly following user example
            target_url = worker_url
            if not target_url:
                raise ValueError("Worker URL required for Cloudflare Image Generation")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "prompt": prompt,
                "model": model or "@cf/stabilityai/stable-diffusion-xl-base-1.0",
                "width": width,
                "height": height,
                "format": "png",
                "quality": 90,
                "download": False,
                "filename": f"gen_{str(uuid.uuid4())[:8]}.png"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(target_url, json=payload, headers=headers, timeout=60.0)
                if response.status_code != 200:
                    raise Exception(f"Cloudflare Worker Error ({response.status_code}): {response.text}")
                return response.content

        elif provider_lower == "huggingface" or provider_lower == "flux":
            # HuggingFace Inference API (Flux/Stable Diffusion)
            repo = model or "black-forest-labs/FLUX.1-schnell"
            url = f"https://api-inference.huggingface.co/models/{repo}"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {"inputs": prompt}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=90.0)
                if response.status_code != 200:
                    raise Exception(f"HuggingFace Error ({response.status_code}): {response.text}")
                return response.content

        elif provider_lower == "leonardo.ai":
            # Leonardo.ai API
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            # Step 1: Create Generation
            gen_url = "https://cloud.leonardo.ai/api/rest/v1/generations"
            payload = {
                "prompt": prompt,
                "width": width,
                "height": height,
                "num_images": 1,
                "modelId": model or "b24e0da2-cd61-4bc1-91a5-e461b65e7512" # SDXL 1.0 default
            }
            
            async with httpx.AsyncClient() as client:
                gen_res = await client.post(gen_url, json=payload, headers=headers)
                if gen_res.status_code != 200:
                    raise Exception(f"Leonardo Create Error: {gen_res.text}")
                
                gen_id = gen_res.json().get("sdGenerationJob", {}).get("generationId")
                
                # Step 2: Poll for completion
                import asyncio
                for _ in range(30): # 30 seconds poll
                    await asyncio.sleep(2)
                    status_url = f"https://cloud.leonardo.ai/api/rest/v1/generations/{gen_id}"
                    status_res = await client.get(status_url, headers=headers)
                    images = status_res.json().get("generations_by_pk", {}).get("generated_images", [])
                    if images:
                        img_url = images[0].get("url")
                        img_res = await client.get(img_url)
                        return img_res.content
                raise Exception("Leonardo.ai Generation Timed Out")

        elif provider_lower == "nvidia":
            # Nvidia NIM API
            url = "https://ai.api.nvidia.com/v1/genai/stabilityai/sdxl" # Placeholder, adjust based on actual model
            if model and "/" in model:
                # If they provide something like nvidia/sdxl-turbo
                url = f"https://ai.api.nvidia.com/v1/genai/{model}"
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            }
            payload = {
                "text_prompts": [{"text": prompt}],
                "cfg_scale": 7,
                "sampler": "K_DPM_2_ANCESTRAL",
                "steps": 30
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code != 200:
                    raise Exception(f"Nvidia API Error: {response.text}")
                
                # Nvidia usually returns JSON with base64 or a URL
                data = response.json()
                import base64
                img_data = data.get("artifacts", [])[0].get("base64")
                if img_data:
                    return base64.b64decode(img_data)
                raise Exception("Nvidia API: No image data returned")

        elif provider_lower == "dalle3":
            # OpenAI Dall-E 3
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            response = await client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size=f"{width}x{height}",
                quality="standard",
                n=1,
            )
            img_url = response.data[0].url
            async with httpx.AsyncClient() as http_client:
                img_res = await http_client.get(img_url)
                return img_res.content

        else:
            raise ValueError(f"Provider {provider} not implemented in backend")

    @staticmethod
    async def validate_image_worker(api_key: str, worker_url: str) -> dict:
        """Verifies if the Image Worker is reachable and authenticated."""
        import httpx
        if not api_key or not worker_url:
            return {"isValid": False, "error": "URL and API Key required"}
            
        headers = {"Authorization": f"Bearer {api_key}"}
        # Try a minimal generation or a specific status endpoint if available. 
        # Since Workers are standard, we try a small 256x256 generation or just a HEAD if supported.
        # Parity: imageService.ts doesn't have a status endpoint, so we just check if it's reachable.
        try:
            async with httpx.AsyncClient() as client:
                # We do a tiny request to verify. Some workers might fail on empty prompt.
                # However, for 1:1 parallax, we just want to see if the URL is valid.
                resp = await client.get(worker_url, headers=headers, timeout=10.0)
                # Cloudflare workers might return 405 for GET, that's fine, it means it's there.
                if resp.status_code in [200, 405, 401]: 
                    if resp.status_code == 401:
                        return {"isValid": False, "error": "Unauthorized (Invalid Key)"}
                    return {"isValid": True}
                else:
                    return {"isValid": False, "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"isValid": False, "error": str(e)}
