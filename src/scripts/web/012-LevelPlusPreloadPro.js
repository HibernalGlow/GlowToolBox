// ==UserScript==

// @name         LevelPlusPreloadPro
// @namespace    http://tampermonkey.net/
// @version      2024-05-22
// @description  try to take over the world!
// @author       ZacharyZzz


// @icon         blob:chrome-extension://iikmkjmpaadaobahmlepeloendndfphd/daa70cd2-b521-4305-bcde-97df1824f003
// @grant        none
// ==/UserScript==
(async function() {
    'use strict';
    // 获取帖子一楼的图片列表（第一张图片是头像）
    async function getImgUrls(href) {
        let doc = await fetchPostAsDom(href);
        let img_urls = [];

        // 检查是否是帖子列表页
        let search_table = doc.querySelector('table[style*="border-top"][style*="border-left"] td');
        if (search_table) {
            // 获取所有链接
            let links = search_table.querySelectorAll('a[href*="read.php?tid="]');
            for (let link of links) {
                // 获取每个链接对应帖子的封面
                let postDoc = await fetchPostAsDom(link.href);
                let firstImg = postDoc.querySelector('div#read_tpc img:not([src*="face"])');
                img_urls.push({
                    url: link.href,
                    title: link.textContent,
                    description: link.nextSibling?.textContent?.trim() || '',
                    coverImg: firstImg ? firstImg.src : 'https://img.chkaja.com/3ad1df0dfddccd8d.png' // 默认图片
                });
            }
        }

        return img_urls;
    }
    // 获取对应链接的dom对象
    async function fetchPostAsDom(href) {
        let post = await fetch(href);
        let text = await post.text();
        let parser = new DOMParser();
        let doc = parser.parseFromString(text, 'text/html');
        return doc;
    }

    // li > div
    //     span > a 标题
    //     span > a > img 预览图
    //     span
    //         span 作者
    //         span 日期/回复/人气
    function createLi(tr) {
        let li = document.createElement("li");
        li.style.float = "left";
        li.style.width = "200px";
        li.style.height = "350px";
        li.style.border = "1px solid #4169E1";
        li.style.margin = "0 12px 12px 0";
        li.style.padding = "3px 3px 15px 3px";
        li.style.position = "relative";
        li.style.boxShadow = "0 1px 2px rgba(0, 0, 0, 0.5)";

        let div = document.createElement("div");

        // 标题
        let span1 = document.createElement("span");
        span1.style.padding = "3px";
        let th_a = tr.querySelector(' a');

        span1.appendChild(th_a);

        // 图片
        let span2 = document.createElement("span");
        let im_a = document.createElement("a");
        im_a.className = "im-a";
        let img = document.createElement("img");
        img.style.border = "1px solid #4169E1";
        img.style.maxWidth = "194px";
        img.style.maxHeight = "300px";
        img.src = "https://img.chkaja.com/adcadfc7898c229f.png"; // 默认加载图片

        im_a.appendChild(img);
        span2.append(im_a);

        // 作者和发帖日期
        let span3 = document.createElement("span");
        span3.style.position = "absolute";
        span3.style.left = "0";
        span3.style.bottom = "0";
        let span31 = document.createElement("span");
        span31.style.float = "left";
        let span32 = document.createElement("span");
        span32.style.float = "right";
        let td_a = tr.querySelector("td.smalltxt.y-style a");
        let date_txt_m = tr.querySelector("td.smalltxt.y-style").textContent.match(/\d{4}-\d{2}-\d{2}/g);
        let date_txt = "";
        if (date_txt_m.length != 0){
            date_txt = "/" + date_txt_m[0];
        }
        let r_txt = tr.querySelector("td.smalltxt+td").textContent;
        let h_txt = tr.querySelector("td.smalltxt+td+td").textContent;
        let rh_txt = "/" + r_txt + "/" + h_txt;

        let da_txt = date_txt + rh_txt;
        span31.appendChild(td_a);
        span32.textContent = da_txt;
        span3.appendChild(span31);
        span3.appendChild(span32);

        div.appendChild(span1);
        div.appendChild(document.createElement("br"));
        div.appendChild(span2);
        div.appendChild(span3);

        li.appendChild(div);

        return li;
    }

    // 获取所有帖子
    var post_list = document.querySelectorAll('tr.tr3');
    let div_main = document.createElement("div");
    let ul = document.createElement("ul");
    ul.style.listStyleType = "none";
    ul.style.display = "block";
    ul.style.marginBlockStart = "1em";
    ul.style.marginBlockEnd = "1em";
    ul.style.marginInlineStart = "0px";
    ul.style.marginInlineEnd = "0px";
    ul.style.paddingInlineStart = "40px";

    div_main.appendChild(ul);
    let div_fr = document.querySelector("div.fr");
    div_fr.parentNode.insertBefore(div_main, div_fr);

    for (let i = 0; i < post_list.length; i++) {
        let tr = post_list[i];
        tr.parentNode.removeChild(tr);
        ul.appendChild(createLi(tr));
    }

    for (let j = 0; j < ul.childNodes.length; j++) {
        let li = ul.childNodes[j];
        let href = li.querySelector(" a").href;
        let img = li.querySelector(" img");
        let im_a = li.querySelector(" a.im-a");

        let postInfo = await getImgUrls(href);
        if (postInfo && postInfo.length > 0) {
            // 设置第一个帖子的封面
            img.src = postInfo[0].coverImg;

            // 点击切换显示其他帖子的封面
            let currentIndex = 0;
            im_a.onclick = () => {
                currentIndex = (currentIndex + 1) % postInfo.length;
                img.src = postInfo[currentIndex].coverImg;
                // 可以选择是否更新标题和描述
                let titleSpan = li.querySelector("span:first-child a");
                if (titleSpan) {
                    titleSpan.textContent = postInfo[currentIndex].title;
                }
            };
        }
    }
})();
