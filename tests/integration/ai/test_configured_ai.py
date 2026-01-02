#!/usr/bin/env python3
"""Test all configured AI services."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from setup_path import setup_test_paths
setup_test_paths()

from dotenv import load_dotenv
load_dotenv()

import asyncio
from app.services.ai_service import AIServiceFactory, GenerationRequest

async def test_configured_services():
    """Test all AI services that have API keys configured."""
    
    services_to_test = []
    
    # Check Gemini
    if os.getenv('GOOGLE_AI_API_KEY'):
        services_to_test.append({
            'provider': 'gemini',
            'api_key': os.getenv('GOOGLE_AI_API_KEY'),
            'model': 'gemini-1.5-pro'
        })
    
    # Check Anthropic
    if os.getenv('ANTHROPIC_API_KEY'):
        services_to_test.append({
            'provider': 'anthropic',
            'api_key': os.getenv('ANTHROPIC_API_KEY'),
            'model': 'claude-3-5-sonnet-20241022'
        })
    
    # Check OpenAI
    if os.getenv('OPENAI_API_KEY'):
        services_to_test.append({
            'provider': 'openai',
            'api_key': os.getenv('OPENAI_API_KEY'),
            'model': 'gpt-4-turbo-preview'
        })
    
    if not services_to_test:
        print("❌ No AI services configured. Set API keys in environment variables:")
        print("   - GOOGLE_AI_API_KEY for Gemini")
        print("   - ANTHROPIC_API_KEY for Claude")
        print("   - OPENAI_API_KEY for GPT")
        return False
    
    print(f"Testing {len(services_to_test)} configured AI service(s)...")
    print("="*60)
    
    test_request = GenerationRequest(
        system_prompt="You are a helpful assistant.",
        user_prompt="Respond with your AI model name in 5 words or less.",
        max_tokens=50,
        temperature=0.1
    )
    
    results = []
    
    for service_config in services_to_test:
        provider = service_config['provider']
        print(f"\n📝 Testing {provider.upper()} ({service_config['model']})...")
        
        try:
            service = AIServiceFactory.create(
                provider=provider,
                api_key=service_config['api_key'],
                model=service_config['model']
            )
            
            response = await service.generate(test_request)
            
            if response and response.content:
                print(f"   ✅ {provider.upper()} works!")
                print(f"   Response: {response.content[:100]}")
                results.append((provider, True, None))
            else:
                print(f"   ❌ {provider.upper()} returned empty response")
                results.append((provider, False, "Empty response"))
                
        except Exception as e:
            print(f"   ❌ {provider.upper()} failed: {e}")
            results.append((provider, False, str(e)))
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY:")
    print("="*60)
    
    working = sum(1 for _, success, _ in results if success)
    failed = len(results) - working
    
    for provider, success, error in results:
        status = "✅ Working" if success else f"❌ Failed: {error}"
        print(f"  {provider.upper()}: {status}")
    
    print(f"\nTotal: {working}/{len(results)} services working")
    
    return failed == 0

async def test_dita_generation():
    """Test DITA generation with available AI services."""
    
    # Find a working AI service
    ai_service = None
    provider_name = None
    
    for provider, api_key_env, model in [
        ('gemini', 'GOOGLE_AI_API_KEY', 'gemini-1.5-pro'),
        ('anthropic', 'ANTHROPIC_API_KEY', 'claude-3-5-sonnet-20241022'),
        ('openai', 'OPENAI_API_KEY', 'gpt-4-turbo-preview')
    ]:
        api_key = os.getenv(api_key_env)
        if api_key:
            try:
                ai_service = AIServiceFactory.create(
                    provider=provider,
                    api_key=api_key,
                    model=model
                )
                provider_name = provider
                break
            except:
                continue
    
    if not ai_service:
        print("❌ No AI service available for DITA generation test")
        return False
    
    print(f"\n📝 Testing DITA generation with {provider_name.upper()}...")
    print("="*60)
    
    dita_request = GenerationRequest(
        system_prompt="You are a DITA XML expert. Generate valid DITA 1.3 XML.",
        user_prompt="""Generate a simple DITA topic with this structure:
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="sample">
  <title>Sample Topic</title>
  <body>
    <p>This is a test topic.</p>
  </body>
</topic>""",
        max_tokens=500,
        temperature=0.1
    )
    
    try:
        response = await ai_service.generate(dita_request)
        
        if response and response.content:
            # Check if it looks like DITA
            if '<?xml' in response.content or '<topic' in response.content:
                print("✅ DITA generation successful!")
                print(f"Generated content preview:\n{response.content[:300]}...")
                return True
            else:
                print("⚠️ Response doesn't look like DITA XML")
                print(f"Response: {response.content[:200]}...")
                return False
        else:
            print("❌ Empty response")
            return False
            
    except Exception as e:
        print(f"❌ DITA generation failed: {e}")
        return False

if __name__ == "__main__":
    print("Configured AI Services Test")
    print("="*60)
    
    # Run basic connectivity tests
    success = asyncio.run(test_configured_services())
    
    if success:
        # Run DITA generation test
        asyncio.run(test_dita_generation())
        print("\n✅ All configured AI services tested successfully!")
    else:
        print("\n⚠️ Some AI services are not working correctly")