from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.db.models import Count
from .models import Cliente, Ticket, PerfilUsuario

User = get_user_model()

@method_decorator(login_required, name='dispatch')
class DashboardView(TemplateView):
    template_name = 'dashboard/index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_clientes'] = Cliente.objects.count()
        
        # Contagem de tickets por status
        tickets_stats = Ticket.objects.values('status').annotate(count=Count('id'))
        context['tickets_abertos'] = sum(item['count'] for item in tickets_stats if item['status'] in ['aberto', 'em_andamento'])
        context['tickets_fechados'] = sum(item['count'] for item in tickets_stats if item['status'] == 'fechado')
        context['total_tickets'] = Ticket.objects.count()
        
        return context

@method_decorator(login_required, name='dispatch')
class ProfileView(TemplateView):
    template_name = 'dashboard/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Busca ou cria o perfil do usuário
        perfil, created = PerfilUsuario.objects.get_or_create(
            user=self.request.user,
            defaults={'telefone': ''}
        )
        context['perfil'] = perfil
        return context
    
    def post(self, request, *args, **kwargs):
        try:
            # Busca ou cria o perfil do usuário
            perfil, created = PerfilUsuario.objects.get_or_create(
                user=request.user,
                defaults={'telefone': ''}
            )
            
            # Atualiza dados básicos do usuário
            user = request.user
            user.first_name = request.POST.get('first_name', '')
            user.last_name = request.POST.get('last_name', '')
            user.email = request.POST.get('email', '')
            user.save()
            
            # Atualiza dados do perfil
            perfil.telefone = request.POST.get('telefone', '')
            perfil.endereco = request.POST.get('endereco', '')
            perfil.bio = request.POST.get('bio', '')
            
            # Processa upload de avatar
            if 'avatar' in request.FILES:
                perfil.avatar = request.FILES['avatar']
            
            perfil.save()
            
            messages.success(request, 'Perfil atualizado com sucesso!')
            
        except Exception as e:
            messages.error(request, f'Erro ao atualizar perfil: {str(e)}')
            
        return redirect('dashboard:profile')
