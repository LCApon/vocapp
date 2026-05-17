// Generic get and post functions
async function get_html(path) {
    const r = await fetch(API + path);
    return r.ok ? r.text() : null;
}

async function post_json(path, body) {
    const r = await fetch(API + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });

    return r.ok ? r.json() : null;
}

async function get_json(path) {
    const r = await fetch(API + path);
    return r.ok ? r.json() : null;
}
