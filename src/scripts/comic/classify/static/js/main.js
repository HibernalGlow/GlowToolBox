// 全局状态
let currentView = 'table';
let artistsData = {
    existing: [],
    new: []
};

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
    initializeBootstrapTable();
});

function setupEventListeners() {
    // 设置全选事件
    document.getElementById('existing-select-all').addEventListener('change', function() {
        toggleSelectAll('existing', this.checked);
    });
    
    document.getElementById('new-select-all').addEventListener('change', function() {
        toggleSelectAll('new', this.checked);
    });

    // 设置导入文件事件
    document.getElementById('importFile').addEventListener('change', handleFileImport);

    // 设置已存在画师显示/隐藏事件
    document.getElementById('toggleExisting').addEventListener('click', function() {
        const content = document.getElementById('existing-content');
        content.style.display = content.style.display === 'none' ? 'block' : 'none';
    });
}

function initializeBootstrapTable() {
    $('#existing-table').bootstrapTable({
        search: true,
        pagination: true,
        pageSize: 10
    });

    $('#new-table').bootstrapTable({
        search: true,
        pagination: true,
        pageSize: 10
    });
}

// 切换视图
function toggleView() {
    currentView = currentView === 'table' ? 'grid' : 'table';
    
    ['existing', 'new'].forEach(section => {
        document.getElementById(`${section}-table-view`).style.display = 
            currentView === 'table' ? 'block' : 'none';
        document.getElementById(`${section}-grid-view`).style.display = 
            currentView === 'grid' ? 'block' : 'none';
    });
}

// 全选/取消全选
function toggleSelectAll(section, checked) {
    const table = document.getElementById(`${section}-table`);
    const checkboxes = table.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(checkbox => checkbox.checked = checked);
    updateArtistsData();
}

// 反选
function invertSelection(section) {
    const table = document.getElementById(`${section}-table`);
    const checkboxes = table.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(checkbox => checkbox.checked = !checkbox.checked);
    updateSelectAllState(section);
    updateArtistsData();
}

// 更新全选框状态
function updateSelectAllState(section) {
    const table = document.getElementById(`${section}-table`);
    const checkboxes = Array.from(table.querySelectorAll('input[type="checkbox"]:not(#${section}-select-all)'));
    const selectAllCheckbox = document.getElementById(`${section}-select-all`);
    selectAllCheckbox.checked = checkboxes.every(cb => cb.checked);
    selectAllCheckbox.indeterminate = checkboxes.some(cb => cb.checked) && !checkboxes.every(cb => cb.checked);
}

// 更新数据状态
function updateArtistsData() {
    ['existing', 'new'].forEach(section => {
        const table = document.getElementById(`${section}-table`);
        artistsData[section] = Array.from(table.querySelectorAll('tbody tr')).map(row => ({
            name: row.querySelector('.artist-name').textContent,
            checked: row.querySelector('input[type="checkbox"]').checked,
            files: Array.from(row.querySelector('.files-list').children).map(item => item.textContent)
        }));
    });
}

// 导出选中内容
function exportSelected(type) {
    updateArtistsData();
    
    // 准备导出数据
    const selectedData = {
        artists: [],
        files: [],
        timestamp: new Date().toISOString(),
        type: type,
        selectionState: artistsData
    };

    ['existing', 'new'].forEach(section => {
        artistsData[section].forEach(artist => {
            if (artist.checked) {
                selectedData.artists.push(artist.name);
                selectedData.files.push(...artist.files);
            }
        });
    });

    // 导出文本文件
    const textContent = type === 'artists' ? selectedData.artists.join('\n') : selectedData.files.join('\n');
    downloadFile(`selected_${type}.txt`, textContent);

    // 导出JSON文件
    downloadFile(`selection_state.json`, JSON.stringify(selectedData, null, 2));
}

// 处理文件导入
async function handleFileImport(event) {
    const file = event.target.files[0];
    if (!file) return;

    try {
        const content = await readFileContent(file);
        
        if (file.name.endsWith('.json')) {
            handleJsonImport(content);
        } else {
            handleTextImport(content);
        }
    } catch (error) {
        console.error('导入文件时出错:', error);
        alert('导入文件时出错');
    }
}

// 读取文件内容
function readFileContent(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = event => resolve(event.target.result);
        reader.onerror = error => reject(error);
        reader.readAsText(file);
    });
}

// 处理JSON导入
function handleJsonImport(content) {
    try {
        const data = JSON.parse(content);
        if (data.selectionState) {
            ['existing', 'new'].forEach(section => {
                const sectionData = data.selectionState[section];
                sectionData.forEach(artist => {
                    const checkbox = document.querySelector(`#${section}-table input[data-artist="${artist.name}"]`);
                    if (checkbox) {
                        checkbox.checked = artist.checked;
                    }
                });
                updateSelectAllState(section);
            });
        }
    } catch (error) {
        console.error('解析JSON文件时出错:', error);
        alert('无效的JSON文件格式');
    }
}

// 处理文本导入
function handleTextImport(content) {
    const names = content.split('\n').map(name => name.trim()).filter(name => name);
    ['existing', 'new'].forEach(section => {
        const table = document.getElementById(`${section}-table`);
        const checkboxes = table.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            const artistName = checkbox.closest('tr').querySelector('.artist-name').textContent;
            checkbox.checked = names.includes(artistName);
        });
        updateSelectAllState(section);
    });
}

// 下载文件
function downloadFile(filename, content) {
    const blob = new Blob([content], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

// 打开预览链接
function openPreview(artistName) {
    const url = `https://www.wn01.uk/search/?q=${encodeURIComponent(artistName)}`;
    window.open(url, '_blank');
} 