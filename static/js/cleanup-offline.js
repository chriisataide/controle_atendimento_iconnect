// Script para limpar indicadores offline existentes
document.addEventListener('DOMContentLoaded', function() {
    // Remove qualquer offline-indicator que possa estar no DOM
    const existingIndicators = document.querySelectorAll('.offline-indicator');
    existingIndicators.forEach(indicator => {
        indicator.remove();
    });
    
    console.log('Limpeza de indicadores offline concluída');
});