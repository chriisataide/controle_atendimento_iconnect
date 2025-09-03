# Controle de Atendimento iConnect - Django

Sistema de controle de atendimento desenvolvido com Django, migrado do template Material Dashboard.

## 🚀 Funcionalidades

- Dashboard interativo com métricas em tempo real
- Controle de atendimentos
- Interface responsiva com Material Design
- Gráficos dinâmicos para análise de dados
- Sistema de notificações
- Gestão de tickets de suporte

## 📋 Pré-requisitos

- Python 3.8+
- pip (gerenciador de pacotes Python)
- Virtualenv (recomendado)

## 🛠️ Instalação

1. Clone o repositório:
```bash
git clone [seu-repositório]
cd controle_atendimento_iconnect
```

2. Crie e ative um ambiente virtual:
```bash
python -m venv .venv
source .venv/bin/activate  # No macOS/Linux
# ou
.venv\Scripts\activate  # No Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Execute as migrações:
```bash
python manage.py migrate
```

5. Inicie o servidor de desenvolvimento:
```bash
python manage.py runserver
```

6. Acesse o sistema em: `http://127.0.0.1:8000`

## 📁 Estrutura do Projeto

```
controle_atendimento_iconnect/
├── controle_atendimento/       # Configurações do projeto Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── dashboard/                  # App principal do dashboard
│   ├── views.py               # Views do dashboard
│   ├── urls.py                # URLs do dashboard
│   └── models.py              # Modelos de dados
├── templates/                  # Templates Django
│   ├── base.html              # Template base
│   └── dashboard/
│       └── index.html         # Dashboard principal
├── assets/                     # Arquivos estáticos (CSS, JS, imagens)
│   ├── css/
│   ├── js/
│   └── img/
├── requirements.txt            # Dependências Python
└── manage.py                  # Utilitário de gerenciamento Django
```

## 🎨 Personalização

### Alterando as métricas do dashboard

Edite o arquivo `dashboard/views.py` para modificar os dados exibidos:

```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['atendimentos_hoje'] = 47  # Altere aqui
    context['usuarios_ativos'] = 23    # Altere aqui
    # ... outros dados
    return context
```

### Modificando a aparência

- **CSS**: Edite os arquivos em `assets/css/`
- **JavaScript**: Modifique `assets/js/`
- **Templates**: Altere os arquivos em `templates/`

## 🔧 Desenvolvimento

### Criando novos apps:
```bash
python manage.py startapp nome_do_app
```

### Criando migrações:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Coletando arquivos estáticos (produção):
```bash
python manage.py collectstatic
```

## 📊 API Endpoints

- `GET /` - Dashboard principal
- `GET /api/` - Dados do dashboard em JSON

## 🐛 Problemas Conhecidos

- Certifique-se de que todas as dependências estão instaladas
- Verifique se a porta 8000 está disponível
- Em caso de erro 404, verifique as configurações de URL

## 📝 Licença

Este projeto está licenciado sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.

## 🤝 Contribuição

1. Faça um Fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## 📞 Suporte

Para dúvidas e suporte, abra uma issue no repositório do projeto.

---

Desenvolvido com ❤️ usando Django e Material Dashboard
