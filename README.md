# Bot Discord em Python

Este projeto transforma seu servidor em um chatbot alimentado por IA usando a API do [OpenRouter](https://openrouter.ai/). É construído sobre o [discordpy](https://discordpy.readthedocs.io/); leia [seus guias de primeiros passos](https://discordpy.readthedocs.io/en/stable/#getting-started) para aproveitar ao máximo este template.

## Começando

Para configurar, você precisa seguir [estas instruções de configuração da conta do bot](https://discordpy.readthedocs.io/en/stable/discord.html), e então copiar o token do seu bot e adicioná-lo como um segredo com a chave `TOKEN` no painel "Secrets (Environment variables)".

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

Se você receber a seguinte mensagem de erro ao tentar iniciar o servidor: `429 Too Many Requests` (acompanhado por muito código HTML), tente o conselho dado nesta pergunta do Stackoverflow: https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests
