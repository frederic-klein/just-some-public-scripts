import http from "k6/http";
import { check } from "k6";

function buildLoginBody(username, password) {
    return {
        uauthlogin: "default",
        state: 1,
        username: username,
        password: password,
      };
}

function initCookies(url) {
  http.get(url);
}

function login(url, loginBody) {
    const loginPath = url.replace(/^(https?:\/\/[^/]*\/)/, "$1bin/login/");
    const res = http.post(loginPath, loginBody, { redirects: 0 });
    return check(res, {
        "login has expected status 302": (r) => r.status === 302,
    });
}

export default function () {
    // k6 run -e PROTOCOL=http -e FQDN=multisite-dev.qwiki -e USERNAME=some_admin -e PASSWORD=some_pw k6-qwiki.js
    const jar = http.cookieJar();
    const url = `${__ENV.PROTOCOL}://${__ENV.FQDN}/`;

    initCookies(url);

    if (!login(url, buildLoginBody(`${__ENV.USERNAME}`, `${__ENV.PASSWORD}`))) {
        console.log("login failed", res.status);
        return;
    }

    const res = http.get(`${url}api/v1/search?context=Processes&q=konti&page=1&additionalContexts=`);

    check(res, {
        "is status 200": (r) => r.status === 200,
    });

    check(res, {
        'verify count of search results': (r) =>
        r.json('elements').length == 4,
    });
}
