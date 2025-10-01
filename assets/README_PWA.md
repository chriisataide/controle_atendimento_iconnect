# PWA e Service Worker

O sistema já possui manifest.json e agora conta com um `service-worker.js` básico para funcionamento offline e cache de assets essenciais.

## Como funciona
- O service worker é registrado automaticamente em `base.html`.
- Ele faz cache dos principais arquivos estáticos e permite navegação offline básica.
- O manifest.json já está configurado para PWA (ícones, tema, nome, etc).

## Próximos passos sugeridos
- Adicionar mais arquivos críticos ao array `urlsToCache` no `service-worker.js`.
- Implementar estratégias de cache mais avançadas (ex: cache first, network first, stale-while-revalidate).
- Exibir um banner ou modal de onboarding para explicar o modo offline ao usuário.
- Testar instalação em dispositivos móveis e uso offline.

## Referências
- [MDN - Service Worker API](https://developer.mozilla.org/pt-BR/docs/Web/API/Service_Worker_API)
- [Checklist PWA Google](https://web.dev/pwa-checklist/)