# Python Discord Bot

This project now turns your server into an AI-powered chatbot using the
[OpenRouter](https://openrouter.ai/) API. It's built on top of
[discordpy](https://discordpy.readthedocs.io/); read
[their getting-started guides](https://discordpy.readthedocs.io/en/stable/#getting-started) to get the most out of this template.

## Getting Started

To get set up, you'll need to follow [these bot account setup instructions](https://discordpy.readthedocs.io/en/stable/discord.html),
and then copy the token for your bot and add it as a secret with the key of `TOKEN` in the "Secrets (Environment variables)" panel.

## Configurando o OpenRouter

1. Crie uma conta no [OpenRouter](https://openrouter.ai/) e gere uma chave de API.
2. Cadastre as seguintes variáveis de ambiente:
   - `OPENROUTER_API_KEY`: **obrigatória**. Chave de API gerada no painel do OpenRouter.
   - `OPENROUTER_MODEL`: opcional. Nome do modelo a ser utilizado (padrão `openrouter/auto`).
   - `OPENROUTER_SYSTEM_PROMPT`: opcional. Texto usado como instrução inicial para o assistente.
   - `OPENROUTER_TIMEOUT`: opcional. Tempo limite (em segundos) para aguardar a resposta da API; padrão `60`.
   - `OPENROUTER_MAX_TURNS`: opcional. Número de trocas de mensagens mantidas no histórico por canal; padrão `6`.
   - `OPENROUTER_REFERER` e `OPENROUTER_TITLE`: opcionais, informam o domínio e nome do app conforme recomenda a documentação do OpenRouter.
3. Execute o bot normalmente. Ele responderá automaticamente a mensagens diretas, menções e respostas aos próprios envios.

## FAQ

If you get the following error message while trying to start the server: `429 Too Many Requests` (accompanied by a lot of HTML code), 
try the advice given in this Stackoverflow question:
https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests
