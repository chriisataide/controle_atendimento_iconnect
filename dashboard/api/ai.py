"""
Endpoint para sugestão automática de prioridade e categoria de ticket via IA/ML.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from ..services.ml_engine import ml_predictor

class TicketAISuggestionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Recebe título e descrição, retorna sugestão de prioridade/categoria."""
        titulo = request.data.get('titulo', '')
        descricao = request.data.get('descricao', '')
        cliente_id = request.data.get('cliente_id')
        if not titulo or not descricao:
            return Response({'error': 'Título e descrição são obrigatórios.'}, status=status.HTTP_400_BAD_REQUEST)
        result = ml_predictor.predict_ticket_properties(titulo, descricao, cliente_id)
        if not result:
            return Response({'error': 'Modelo não treinado ou insuficiente.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(result)
