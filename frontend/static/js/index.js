let calculatedGroups = {};

document.addEventListener('DOMContentLoaded', function() {
  const uploadForm = document.getElementById('uploadForm');
  const fileInput = document.getElementById('fileInput');
  const progressBar = document.getElementById('progressBar');
  const uploadMessage = document.getElementById('upload_message');
  

  uploadForm.addEventListener('submit', function(event) {
    event.preventDefault();

    if (fileInput.files.length === 0) {
      uploadMessage.textContent = 'Пожалуйста, выберите файл.';
      return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload-csv/', true);

    xhr.upload.onprogress = function(e) {
      if (e.lengthComputable) {
        const percentComplete = (e.loaded / e.total) * 100;
        progressBar.value = percentComplete;
        progressBar.style.display = 'block';
      }
    };

    xhr.onload = async function() {
      if (xhr.status === 200) {
        uploadMessage.textContent = 'Файл успешно загружен.';
        progressBar.style.display = 'none';
        PrintData();
      } else {
        uploadMessage.textContent = 'Ошибка при загрузке файла.';
        progressBar.style.display = 'none';
      }
    };

    xhr.onerror = function() {
      uploadMessage.textContent = 'Ошибка при загрузке файла.';
      progressBar.style.display = 'none';
    };

    xhr.send(formData);
  });
});

async function PrintData() {
  console.log("printData")
  const jsonStatsOutput = document.getElementById('json_stats_output');
  try {
    const response = await fetch("/get_data_stats");
    const data = await response.json();
    jsonStatsOutput.innerHTML = "";

    const basicInfo = document.createElement("div");
    basicInfo.innerHTML = `<strong>Количество строк:</strong> ${data.num_rows}<br>
                          <strong>Количество столбцов:</strong> ${data.num_columns}`;
    jsonStatsOutput.appendChild(basicInfo);

    const columns = data.column_info;
    for (const col in columns) {
      if (columns.hasOwnProperty(col)) {
        const colDiv = document.createElement("div");
        let colInfo = `<strong>${col}</strong>:<br>`;
        const info = columns[col];
        for (const key in info) {
          if (info.hasOwnProperty(key)) {
            colInfo += `${key}: ${info[key]}<br>`;
          }
        }
        colDiv.innerHTML = colInfo;
        jsonStatsOutput.appendChild(colDiv);
      }
    }
  } catch (error) {
    console.error("Ошибка при получении статистики данных:", error);
  }
  
}

async function StartAlg() {
  PrintData();
  console.log("Запуск алгоритма");
  try {
    const response = await fetch("/calculate_all");
    const data = await response.json();

    calculatedGroups = {};
    Object.keys(data).forEach(key => {
      const group = data[key];
      calculatedGroups[group.id] = group;
    });

    PrintGroups(data);
    console.log("Response:", data);
  } catch (error) {
    console.error("Ошибка при выполнении запроса:", error);
  }
}

async function PrintGroups(data) {
  const container = document.getElementById("groups");
  if (!container) {
    console.error('Элемент с id "groups" не найден.');
    return;
  }
  container.innerHTML = "";
  Object.keys(data).forEach(key => {
    const groupData = data[key];
    if (!groupData || typeof groupData !== "object") return;
    const newGroupItem = document.createElement("div");
    newGroupItem.classList.add("group-item");

    const label = document.createElement("label");
    label.textContent = `номер группы ${groupData.id}, ошибка ${groupData.error}`;
    newGroupItem.appendChild(label);

    const btn = document.createElement("button");
    btn.type = "button";
    btn.classList.add("show-button");
    btn.textContent = "-";
    btn.addEventListener("click", function() {
      ShowGroupPlot(groupData.id);
    });
    newGroupItem.appendChild(btn);

    container.appendChild(newGroupItem);
  });
}

async function ShowGroupPlot(group_id) {
  console.log("Функция ShowGroupPlot вызвана, group_id:", group_id);
  try {
    const container = document.getElementById("load-plot");
    container.innerHTML = "";
    const imgSrc = calculatedGroups[group_id]['img'];
    const img = document.createElement('img');
    img.src = `data:image/png;base64,${imgSrc}`;
    img.classList.add("img-fluid");
    container.appendChild(img);
    console.log("Изображение добавлено");
  } catch (err) {
    console.error("Ошибка в ShowGroupPlot:", err);
  }
}
window.ShowGroupPlot = ShowGroupPlot;