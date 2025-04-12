function sortTable(column) {
    let url = new URL(window.location.href);
    let params = new URLSearchParams(url.search);
    
    params.set('sort', column);
    
    const currentSort = params.get('sort');
    const currentOrder = params.get('order');
    
    if (column === currentSort) {
        params.set('order', currentOrder === 'asc' ? 'desc' : 'asc');
    } else {
        params.set('order', 'asc');
    }
    
    if (!params.has('page')) {
        params.set('page', '1');
    }
    
    url.search = params.toString();
    window.location.href = url.toString();
}

document.addEventListener('DOMContentLoaded', () => {
    const searchForm = document.getElementById('userSearchForm');
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const searchInput = document.getElementById('userSearchInput');
            
            let url = new URL(window.location.href);
            let params = new URLSearchParams(url.search);
            
            if (searchInput.value) {
                params.set('search', searchInput.value);
            } else {
                params.delete('search');
            }
            params.set('page', '1');
            
            url.search = params.toString();
            window.location.href = url.toString();
        });
    }
});

function handleWebSocketMessage(data) {
    if (data.type === 'system_stats') {
        const activeUsersElement = document.getElementById('activeUsers');
        if (activeUsersElement && data.data.active_users !== undefined) {
            activeUsersElement.textContent = `${data.data.active_users} / ${data.data.total_users}`;
            
            const activePercentage = data.data.total_users > 0 
                ? (data.data.active_users / data.data.total_users) * 100 
                : 0;

            const progressBar = activeUsersElement.closest('.stats-card').querySelector('.progress-bar');
            if (progressBar) {
                progressBar.style.width = `${activePercentage}%`;
            }
        }
    }
}
